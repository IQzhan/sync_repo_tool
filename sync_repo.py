import sys
import os
import json
import subprocess
import shutil

# Function to convert a path to an absolute path
def ConvertToAbsolutePath(path, configFilePath):
    if os.path.isabs(path):
        return path
    else:
        return os.path.abspath(os.path.join(os.path.dirname(configFilePath), path))

# Function to find all '<prefix><name>.json' files in the specified path
def FindRepositoriesFiles(path, prefix):
    repositoriesFiles = []
    for root, dirs, files in os.walk(path):
        for file in files:
            filePath = os.path.join(root, file)
            if os.path.isfile(filePath) and file.startswith(prefix) and file.endswith('.json'):
                repositoriesFiles.append(filePath)
    return repositoriesFiles

# Function to extract repository configuration from a '<prefix><name>.json' file
def ExtractRepositoryConfigs(filePath):
    configs = []
    with open(filePath, 'r') as f:
        data = json.load(f)
        for config in data:
            repoType = config['type']
            url = config['url']
            branch = config['branch']
            path = ConvertToAbsolutePath(config['path'], filePath)
            version = config['version']
            configs.append({
                'type': repoType,
                'url': url,
                'branch': branch,
                'path': path,
                'version': version,
            })
    return configs

# Function to merge repository configurations with the same repository url and target path
def MergeRepositoryConfigs(configs):
    mergedConfigs = {}
    for config in configs:
        path = config['path']
        key = path
        if key in mergedConfigs:
            versionGreater = mergedConfigs[key]['version'] - config['version']
            if versionGreater <= 0:
                mergedConfigs[key] = config
        else:
            mergedConfigs[key] = config
    return list(mergedConfigs.values())

# Main function to retrieve and merge repository configurations
def RetrieveAndMergeRepositoryConfigs(path, prefix):
    configs = []
    repositories_files = FindRepositoriesFiles(path, prefix)
    for file in repositories_files:
        configs += ExtractRepositoryConfigs(file)
    return MergeRepositoryConfigs(configs)

def ReadStartConfig(filePath):
    with open(filePath, 'r') as f:
        data = json.load(f)
        targetPath = data['path']
        data['path'] = ConvertToAbsolutePath(targetPath, filePath)
    return data

def UpdateGitRepository(config):
    url = config['url']
    branch = config['branch']
    targetPath = config['path']
    # check if the local path exists
    if not os.path.exists(targetPath):
        # if the local path does not exist
        # Clone the repository
        subprocess.run(['git', 'clone', url, targetPath])
    else:
        # if the local path exists, check if it's a git repository and if it's the same as the remote
        targetGitPath = os.path.join(targetPath, '.git')
        needGitFolder = False
        if os.path.exists(targetGitPath):
            # if it's a git repository, check if it's the same as the remote
            isRepo = False
            try:
                repoUrlOutput = subprocess.run(
                    ['git', '-C', targetPath, 'config', '--get', 'remote.origin.url'],
                    stdout=subprocess.PIPE,
                    check=True,
                )
                repoUrlOutput = repoUrlOutput.stdout.decode().strip()
                if repoUrlOutput == url:
                    isRepo = True
            except subprocess.CalledProcessError:
                return
            if not isRepo:
                # if the current remote is not the same as the desired remote
                # Remove '.git' folder
                shutil.rmtree(targetGitPath)
                needGitFolder = True
        else:
            # if the local path is not a git repository
            needGitFolder = True
        if needGitFolder:
            # Clone into a temp folder then move to targetPath
            tempPath = os.path.join(targetPath, "temp_path")
            shutil.rmtree(tempPath)
            subprocess.run(['git', 'clone', '--no-checkout', url, tempPath])
            shutil.move(os.path.join(tempPath, '.git'), targetPath)
            shutil.rmtree(tempPath)
    # Checkout the specified branch or tag
    subprocess.run(['git', '-C', targetPath, 'checkout', branch, '--force'])
    # If in branch, force update to the latest version
    subprocess.run(['git', '-C', targetPath, 'pull', '--force'])
    return

def UpdateSvnRepository(config):
    url = config['url']
    targetPath = config['path']
    # Check out the repository from the specified URL and branch or tag
    subprocess.run(['svn', 'checkout', '--force', url, '--revision', 'HEAD', targetPath])
    # Force update to the latest version
    subprocess.run(['svn', 'update', '--force', '--accept=theirs-full', targetPath])
    # Revert any changes if there is no update
    subprocess.run(['svn', 'revert', '--depth', 'infinity', targetPath])
    return

def UpdateAllRepositories(configs):
    for config in configs:
        if config['type'] == 'git':
            UpdateGitRepository(config)
        elif config['type'] == 'svn':
            UpdateSvnRepository(config)
    return

def ExecuteMain():
    configPath = None
    if len(sys.argv) > 1:
        configPath = sys.argv[1]
    else:
        configPath = input("Input config path: ")
    if os.path.isfile(configPath) and configPath.endswith('.json'):
        startConfig = ReadStartConfig(configPath)
        configs = RetrieveAndMergeRepositoryConfigs(startConfig['path'], startConfig['prefix'])
        UpdateAllRepositories(configs)
        print(configs)
    return

if __name__ == "__main__":
    ExecuteMain()
