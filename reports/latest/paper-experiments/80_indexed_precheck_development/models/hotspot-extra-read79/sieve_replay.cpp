#include "sieve_policy.h"
#include <fstream>
#include <iostream>
#include <list>
#include <algorithm>
using namespace tokenfs_policy;
int main(int argc,char** argv){
 if(argc!=3)return 2;std::ifstream in(argv[1]);std::ofstream out(argv[2]);
 out<<"kind\tarm\tobservation\tkey\tdetail\n";
 SievePolicy p;std::unordered_set<std::string> disk;std::list<std::string> ram;
 int caller,i=0,remote=0,local=0,captured_count=0;std::string key;
 while(in>>key>>caller){++i;bool exists=disk.count(key),captured=std::find(ram.begin(),ram.end(),key)!=ram.end();
  if(exists)p.HitKnown(0,key);
  out<<"request\tPoolSIEVE1\t"<<i<<'\t'<<key<<'\t'<<captured<<":"<<exists<<'\n';
  ram.remove(key);ram.push_back(key);if(ram.size()>2){out<<"ram_evict\tPoolSIEVE1\t"<<i<<'\t'<<ram.front()<<"\tlru\n";ram.pop_front();}
  if(captured){++captured_count;continue;}if(exists){++local;continue;}++remote;
  out<<"copy\tPoolSIEVE1\t"<<i<<'\t'<<key<<"\t0";
  if(disk.size()>=12){auto victim=p.Victim(0,disk);if(victim.empty())return 3;disk.erase(victim);p.Removed(0,victim);out<<":"<<victim;}
  disk.insert(key);p.Ready(0,key);out<<'\n';
 }
 std::cout<<"remote="<<remote<<" disk_hits="<<local<<" ram_hits="<<captured_count<<" copies="<<remote<<'\n';
}
