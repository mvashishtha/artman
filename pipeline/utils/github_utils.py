# Copyright 2016 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Utility functions related to GitHub interaction. Uses the GitHub API with
reference https://developer.github.com/v3/"""

import requests
import json
import os

_API_URL = 'https://api.github.com'
# file modes for different git file types
_TREE_EL_MODES = {'file': u'100644',
                  'executable': u'100755',
                  'tree': u'040000',
                  'symlink': u'120000'}
_REQUEST_FUNCS = {'GET': requests.get,
                  'POST': requests.post,
                  'PATCH': requests.patch}


def _is_executable(el):
    return os.path.isfile(el) and os.access(el, os.X_OK)


def _get_immediate_subdirs(a_dir):
    return filter(lambda x: os.path.isdir(os.path.join(a_dir, x)),
                  os.listdir(a_dir))


def _get_immediate_files(a_dir):
    return filter(lambda x: os.path.isfile(os.path.join(a_dir, x)),
                  os.listdir(a_dir))


def _exec_request(http_method, url, req_data=None, username=None,
                  password=None):
    """Make an HTTP request with given data and (username, password) tuple.
    Return json response if request succeeds, otherwise raise an exception"""
    request_func = _REQUEST_FUNCS[http_method]
    if username and password:
        attempt = request_func(url, data=req_data, auth=(username, password))
    else:
        attempt = request_func(url, data=req_data)
    if attempt.ok:
        return json.loads(attempt.content)
    else:
        raise Exception(
            'Failed request at {0}. Reason: {1}'.format(url, attempt.content))


def _get_subtree_sha(orig_tree, path):
    tree_mode = _TREE_EL_MODES['tree']
    gen = (x for x in orig_tree['tree'] if (x['path'] == path and
                                            x['mode'] == tree_mode))
    subtree_item = next(gen, None)
    if subtree_item:
        return subtree_item['sha']


# TODO: Have this function also upload symlinks to the repository
# according to GitHub protocol
def _extend_git_tree(curr_dir, username, password, base_url,
                     orig_tree_sha=None):
    if orig_tree_sha:
        orig_tree = _exec_request(
            'GET', base_url + 'git/trees/{0}'.format(orig_tree_sha))
    tree_els = []
    for subdir in _get_immediate_subdirs(curr_dir):
        if orig_tree_sha:
            subtree_sha = _get_subtree_sha(orig_tree, subdir)
        else:
            subtree_sha = None
        subtree = _extend_git_tree(
            os.path.join(curr_dir, subdir), username, password, base_url,
            subtree_sha)
        tree_els.append({'path': subdir, 'mode': _TREE_EL_MODES['tree'],
                         'type': 'tree', 'sha': subtree['sha']})
    for exec_or_file in _get_immediate_files(curr_dir):
        with open(os.path.join(curr_dir, exec_or_file), 'r') as f:
            path_content = f.read()
        mode = _TREE_EL_MODES['file']
        if _is_executable(os.path.join(curr_dir, exec_or_file)):
            mode = _TREE_EL_MODES['executable']
        tree_els.append({'path': exec_or_file, 'mode': mode, 'type': 'blob',
                         'content': path_content})
    data_dict = {'tree': tree_els}
    if orig_tree_sha:
        data_dict['base_tree'] = orig_tree_sha
    if not tree_els:
        raise Exception("Cannot create empty folder {0} in Git".format(
            curr_dir))
    return _exec_request('POST', base_url + 'git/trees',
                         json.dumps(data_dict), username, password)


def push_dir_github(output_dir, username, password, owner, repo, branch,
                    message='Automated commit from artman'):
    """ Push all content in output_dir to the given GitHub repo branch"""
    base_url = '{0}/repos/{1}/{2}/'.format(_API_URL, owner, repo)
    # get the sha of the latest commit on this branch
    branch_item = _exec_request(
        'GET',
        base_url + 'branches/{0}'.format(branch))
    commit_sha = branch_item['commit']['sha']
    orig_tree_sha = branch_item['commit']['commit']['tree']['sha']
    root_tree = _extend_git_tree(output_dir, username, password,
                                 base_url, orig_tree_sha)
    # make a new commit using the built tree, with the previous commit as its
    # only parent
    req_data = json.dumps({'tree': root_tree['sha'],
                           'parents': [commit_sha], 'message': message})
    new_commit_item = _exec_request('POST',
                                    base_url + 'git/commits', req_data,
                                    username, password)
    # update the repository's refs so that the branch head is the new commit
    _exec_request('PATCH',
                  base_url + 'git/refs/heads/{0}'.format(branch),
                  json.dumps({'sha': new_commit_item['sha'],
                              'force': True}),
                  username, password)
