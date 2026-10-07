#include "../src/sieve_policy.h"
#include <cassert>
#include <deque>
#include <random>
#include <iostream>
#include <unordered_set>
using tokenfs_policy::SievePolicy;

// Independent array reference: oldest first, increasing cursor, insertion at end.
struct Reference {
  struct Entry {std::string key; bool visited;};
  std::deque<Entry> queue;
  size_t hand=0;
  std::string access(const std::string& key,size_t capacity) {
    for(auto& e:queue)if(e.key==key){e.visited=true;return {};}
    std::string evicted;
    if(queue.size()==capacity) {
      hand%=queue.size();
      while(queue[hand].visited){queue[hand].visited=false;hand=(hand+1)%queue.size();}
      evicted=queue[hand].key;
      queue.erase(queue.begin()+hand);
      if(hand==queue.size())hand=0; // At newest, restart from oldest after insertion.
    }
    queue.push_back({key,false});
    return evicted;
  }
};
int main(){
  for(size_t capacity=1;capacity<=16;++capacity){
    SievePolicy sieve; Reference ref;std::unordered_set<std::string> residents;
    std::mt19937 rng(97+capacity);
    for(int i=0;i<5000;++i){
      const auto key=std::to_string(rng()%31);const auto expected=ref.access(key,capacity);
      if(residents.count(key)){assert(expected.empty());sieve.Hit(0,key);}
      else {
        if(residents.size()==capacity){
          auto victim=sieve.Victim(0,residents);assert(victim==expected);
          sieve.Removed(0,victim);residents.erase(victim);
        } else assert(expected.empty());
        sieve.Ready(0,key);residents.insert(key);
      }
    }
  }
  SievePolicy isolated;
  isolated.Ready(0,"a");isolated.Ready(0,"b");isolated.Hit(0,"a");
  isolated.Ready(1,"a");isolated.Ready(1,"b");
  assert(isolated.Victim(1,{"a","b"})=="a");
  assert(isolated.Victim(0,{"a","b"})=="b");
  isolated.Removed(0,"b");assert(isolated.Victim(0,{"missing"}).empty());
  assert(isolated.Victim(0,{"a"})=="a");
  isolated.Removed(0,"a");assert(isolated.Victim(0,{"a"}).empty());
  SievePolicy upper_tier;
  assert(!upper_tier.HitKnown(9,"never-published"));
  assert(upper_tier.Victim(9,{"never-published"}).empty());
  upper_tier.Ready(0,"a");upper_tier.Ready(0,"b");
  assert(!upper_tier.HitKnown(1,"a"));
  assert(upper_tier.HitKnown(0,"a"));
  assert(upper_tier.Victim(0,{"a","b"})=="b");
  upper_tier.Removed(0,"a");assert(!upper_tier.HitKnown(0,"a"));
  std::cout<<"SIEVE reference equivalence: 80000 accesses; isolation/pinning passed\n";
}
