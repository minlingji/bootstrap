#!/usr/bin/env python
# -*- coding: utf-8 -*-

from git import Repo, RemoteProgress
import os, sys

MAX_RETRY = 3

class MyProgressPrinter(RemoteProgress):
    def update(self, op_code, cur_count, max_count=None, message=''):
        print(op_code, cur_count, max_count, cur_count / (max_count or 100.0), message or "NO MESSAGE")

def print_success():
    print """
     #####  #     #  #####   #####  #######  #####   #####     ###
    #     # #     # #     # #     # #       #     # #     #    ###
    #       #     # #       #       #       #       #          ###
     #####  #     # #       #       #####    #####   #####      #
          # #     # #       #       #             #       #
    #     # #     # #     # #     # #       #     # #     #    ###
     #####   #####   #####   #####  #######  #####   #####     ###

    """

def production_sync(repo, msg = ""):
    # stage results first, then commit, then reset all other files
    repo.index.add(["2.SushiID/label_dont_touch/*.result.csv"])
    if repo.is_dirty(working_tree=False):
        repo.index.commit("Sync production results. " + msg)

    repo.head.reset(index=True, working_tree=True)
    
    # try to push, if rejected, try tp pull first, then retry 
    origin = repo.remotes['origin']
    retry = 0
    while retry < MAX_RETRY:
        retry += 1
        origin.pull(repo.head.reference, progress=MyProgressPrinter())

        push_infos = origin.push(repo.head.reference, progress=MyProgressPrinter())
        if len(push_infos) > 1:
            print "Push should return exactly 1 PushInfo. Abort."
            return
        elif len(push_infos) < 1:
            continue
        push_info = push_infos[0]
        if push_info.flags & push_info.ERROR:
            continue
            
        retry = 0
        break
        
    if retry >= MAX_RETRY:
        print "Push or pull failed with MAX_RETRY: check network first."
        return
    
    print_success()

def production_init(repo_url, local_path):
    if os.path.exists(local_path):
        print "Path '%s' already exists. Use another name or delete the old one. Abort" % local_path
        return

    repo = Repo.init(local_path)
    origin = repo.create_remote('origin', repo_url)
    origin.fetch(progress=MyProgressPrinter())
    
    print "Please choose from the following branches:"
    for i in range(0, len(origin.refs)):
        print "    %d : " % i + origin.refs[i].name
    b = int(raw_input("Input the brance number:"))
    if b > len(origin.refs):
        print "Input wrong. Abort"
        return
    
    branch_name = origin.refs[b].name.split("/")
    branch_name = branch_name[-1]
    # Setup a local tracking branch of a remote branch
    h = repo.create_head(branch_name, origin.refs[b])
    h.set_tracking_branch(origin.refs[b])
    repo.head.reference = h

def main():
    if (len(sys.argv) < 2):
        print "%s sync" % sys.argv[0]
        print "%s init repo_name" % sys.argv[0]
        return
    
    if sys.argv[1] == 'sync':
        try:
            repo = Repo(os.path.dirname(os.path.realpath(__file__)) + "\\..\\")
        except:
            print "Current dir is not a git repo."
            return
        production_sync(repo)
    elif sys.argv[1] == 'init':
        prod_repo_name = sys.argv[2]
        repo_url = "git@git.huantengsmart.com:production/%s.git" % prod_repo_name
        repo_local_path = prod_repo_name
        production_init(repo_url, repo_local_path)

if __name__ == "__main__":
    main()
