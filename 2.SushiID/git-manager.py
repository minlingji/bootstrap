#!/usr/bin/env python
# -*- coding: utf-8 -*-

from git import Repo
import os, sys

class MyProgressPrinter(RemoteProgress):
    def update(self, op_code, cur_count, max_count=None, message=''):
        print(op_code, cur_count, max_count, cur_count / (max_count or 100.0), message or "NO MESSAGE")

def production_sync(repo, msg = ""):
    repo.index.add(["2.SushiID/label_dont_touch/*.result.csv"])
    if repo.is_dirty(working_tree=False):
        repo.index.commit("Sync production results. " + msg)
    repo.head.reset(index=True, working_tree=True)
    
    origin = repo.remotes['origin']
    for push_info in origin.push(repo.head.reference, progress=MyProgressPrinter()):
        print "Pushed"

def main():
    if (len(sys.argv) < 2):
        print "%s sync-update|sync" % sys.argv[0]
        return
    
    print os.path.dirname(os.path.realpath(__file__))
    repo = Repo(os.path.dirname(os.path.realpath(__file__)) + "\\..\\")
    
    if sys.argv[1] == 'sync-update':
        production_sync(repo, "Sync before update")
        production_update(repo)
    elif sys.argv[1] == 'sync':
        production_sync(repo)

if __name__ == "__main__":
    main()
