#include <algorithm>
#include <chrono>
#include <dirent.h>
#include <errno.h>
#include <fstream>
#include <iostream>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string>
#include <sys/types.h>
#include <thread>
#include <unistd.h>
#include <vector>

using namespace std;

bool is_number(const string &s) {
    return (!s.empty() && find_if(s.begin(), s.end(), [](char c) {
                              return !isdigit(c);
                          }) == s.end());
}

string do_readlink(string const &path) {
    char buff[PATH_MAX];
    ssize_t len = ::readlink(path.c_str(), buff, sizeof(buff) - 1);
    if (len != -1) {
        buff[len] = '\0';
        return string(buff);
    } else {
        perror(path.c_str());
        return {};
    }
}

int getProcIdByName(string procName) {
    int pid = -1;

    // Open the /proc directory
    DIR *dp = opendir("/proc");
    if (dp != NULL) {
        // Enumerate all entries in directory until process found
        struct dirent *dirp;
        while (pid < 0 && (dirp = readdir(dp))) {
            // Skip non-numeric entries
            int id = atoi(dirp->d_name);
            if (id > 0) {
                // Read contents of virtual /proc/{pid}/cmdline file
                string cmdPath = string("/proc/") + dirp->d_name + "/cmdline";
                ifstream cmdFile(cmdPath.c_str());
                string cmdLine;
                getline(cmdFile, cmdLine);
                if (!cmdLine.empty()) {
                    // Keep first cmdline item which contains the program path
                    size_t pos = cmdLine.find('\0');
                    if (pos != string::npos)
                        cmdLine = cmdLine.substr(0, pos);
                    // Keep program name only, removing the path
                    pos = cmdLine.rfind('/');
                    if (pos != string::npos)
                        cmdLine = cmdLine.substr(pos + 1);
                    // Compare against requested process name
                    if (procName == cmdLine)
                        pid = id;
                }
            }
        }
    }

    closedir(dp);

    return pid;
}

bool vdrHasOpenSoundDevices() {
    int pid = getProcIdByName(string{"vdr"});
    string fdDirectory = string("/proc/") + to_string(pid) + "/fd/";
    DIR *dp = opendir(fdDirectory.c_str());
    if (dp != NULL) {
        // cout << "reading dir " << fdDirectory << endl;
        struct dirent *dirp;
        while ((dirp = readdir(dp))) {
            string fd_num = dirp->d_name;
            // cout << "checking file " << fd_num << endl;
            if (is_number(fd_num)) {
                string target;
                target = do_readlink(fdDirectory + fd_num);
                if (!target.empty() &&
                    (target.find("/dev/snd/") != string::npos)) {
                    return true;
                }
            }
        }
    }
    closedir(dp);
    return false;
}

int main() {
    if (setuid(0) != 0) {
        cerr << "Error: this programm must be run as root" << endl;
        return 1;
    }

    constexpr chrono::milliseconds sleep_duration(25);
    constexpr uint32_t max_cycles =
        (chrono::seconds(5) / sleep_duration); // wait up to 5 seconds
    uint32_t cycles = 0;

    while (vdrHasOpenSoundDevices() and cycles <= max_cycles) {
        this_thread::sleep_for(sleep_duration);
        cycles++;
    }
    return 0;
}
