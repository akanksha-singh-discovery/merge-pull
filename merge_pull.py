#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2016/2017 Reinhard Nägele
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

from __future__ import print_function
from __future__ import unicode_literals
from builtins import input

import sys
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from subprocess import Popen, STDOUT, PIPE

args_parser = ArgumentParser(formatter_class=ArgumentDefaultsHelpFormatter, description='''
    Merges a Bitbucket pull request. Multiple commits are squashed. The commits are then rebased on top
    of upstream changes and pushed directly to the feature branch and the target branch. Bitbucket regognizes this
    and marks the pull request as merged. Then switches to the target branch and deletes the feature branch.''')
args_parser.add_argument('--target-branch', '-t', default='master', help='The target_branch of the pull request')
args_parser.add_argument('--remote', '-r', default='origin', help='The name of the remote')
args_parser.add_argument('--message', '-m', help='''If commits need to be squashed, a commit message for the final
    commit is required. You will be prompted to re-use the message of the first commit on the feature branch. You may
    then decide to enter a different message''')
args_parser.add_argument('--assume-yes', '-y', action="store_true", help='Automatic yes to prompts')

args = args_parser.parse_args()

target_branch = args.target_branch
remote = args.remote
message = args.message
assume_yes = args.assume_yes


def git(*arguments):
    cmdline = ['git']
    cmdline.extend(arguments)

    print('')
    print(' '.join(arg for arg in cmdline))

    proc = Popen(cmdline, stdout=PIPE, stderr=STDOUT)
    print('')
    output = []
    while True:
        line = proc.stdout.readline()
        if not line:
            break

        line = line.rstrip().decode('utf-8')
        print('git> {0}'.format(line))
        output.append(line)

    print()
    return_code = proc.wait()
    if return_code != 0:
        print()
        print('Git command terminated with exit code {0}.'.format(return_code))
        sys.exit(1)

    return output


target_branch_remote = '{0}/{1}'.format(remote, target_branch)
feature_branch = git('rev-parse', '--abbrev-ref', '--verify', 'HEAD')[0]
target_branch_ref = git('rev-parse', target_branch)[0]
feature_branch_ref = git('rev-parse', feature_branch)[0]

print('Merging pull request for branch {0} with target branch {1}...'.format(feature_branch, target_branch))

if target_branch_ref == feature_branch_ref:
    print('Target branch and HEAD point to the same ref. Make sure you are on your feature branch.')
    sys.exit(1)

print('Fetching upstream changes...')
git('fetch', remote)

# We need to get a full rev-list using the '...' notation in order to account for
# merges of the target branch into our feature branch.
commits = git('rev-list', '--left-right', '--reverse', 'HEAD...{0}'.format(target_branch_remote))

# Since we retrieved the list in reverse order, we need to look for the first commit on our side (left)
# and strip off the '<' sign.
first_commit_on_branch = next(commit for commit in commits if commit.startswith('<'))[1:]
head_sha1 = git('rev-parse', 'HEAD')[0]

# If the identified commit is the same as HEAD, we know there is only one commit and simply rebase the branch.
# Otherwise we merge and squash.
if first_commit_on_branch == head_sha1:
    print('Rebasing commit(s)...')
    git('rebase', target_branch_remote)
else:
    msg_of_first_commit = '\n'.join(git('show', '--no-patch', '--format=%B', first_commit_on_branch))

    print('Merging in upstream changes...')
    git('merge', target_branch_remote)

    print('Squashing commits...')
    git('reset', '--soft', target_branch_remote)

    if not message:
        print('Message of the first commit on this branch:')
        print('----')
        print()
        print(msg_of_first_commit)
        print()
        print('----')

        if assume_yes or 'y' == input('Re-use the this message (y/N): ').lower():
            print('Re-using commit messsage...')
            message = msg_of_first_commit
        else:
            print('Enter/paste your message. Hit Ctrl-D to save it.')
            contents = []
            while True:
                try:
                    msg_line = input('')
                except EOFError:
                    break
                contents.append(msg_line)
            message = '\n'.join(contents)

    git('commit', '-m', message)

print('Force-pushing commit to feature branch...')
git('push', '--force', remote, 'HEAD:{0}'.format(feature_branch))

print('Pushing commit to target branch...')
git('push', remote, 'HEAD:{0}'.format(target_branch))

print('Switching to target branch...')
git('checkout', target_branch)

print('Pulling in upstream changes...')
git('pull', remote, target_branch, '--rebase')

if assume_yes or 'y' == input('Delete feature branches (y/N): ').lower():
    print('Deleting feature branch...')
    git('branch', '-d', feature_branch)

    print('Deleting feature branch on server...')
    git('push', remote, feature_branch, '--delete')

print('Good bye.')
