#pragma once
#include <list>
#include <mutex>
#include <string>
#include <unordered_map>
#include <unordered_set>

namespace tokenfs_policy {
// SIEVE (NSDI 2024): insertion order, visited bits and a persistent eviction hand.
// This adapter shares TokenFS's asynchronous verified-copy data path. It does not
// claim the original implementation's lock-free hit throughput. Empty-cache
// experiments register residents only when a verified copy is ready to publish.
class SievePolicy {
 public:
  void Ready(int domain, const std::string& key) {
    std::lock_guard<std::mutex> lock(mu_);
    auto& d = domains_[domain];
    if (d.index.count(key)) return;
    d.queue.push_front({key, false});
    d.index.emplace(key, d.queue.begin());
  }
  void Hit(int domain, const std::string& key) {
    (void)HitKnown(domain,key);
  }
  // A logical access can be served by an upper RAM tier while still marking
  // an existing disk resident visited. Never create a resident (or a domain)
  // from an access; only verified Ready publication can do that.
  bool HitKnown(int domain,const std::string& key) {
    std::lock_guard<std::mutex> lock(mu_);
    const auto found=domains_.find(domain);
    if(found==domains_.end())return false;
    auto it=found->second.index.find(key);
    if(it==found->second.index.end())return false;
    it->second->visited=true;return true;
  }
  // Pinned or otherwise unavailable objects cannot be evicted. At most two
  // revolutions are needed: the first clears visited bits of eligible objects.
  std::string Victim(int domain, const std::unordered_set<std::string>& eligible) {
    std::lock_guard<std::mutex> lock(mu_);
    auto& d = domains_[domain];
    if (d.queue.empty() || eligible.empty()) return {};
    auto it = d.index.count(d.hand) ? d.index.at(d.hand) : std::prev(d.queue.end());
    for (size_t n = 0; n < 2 * d.queue.size(); ++n) {
      auto next = it == d.queue.begin() ? d.queue.end() : std::prev(it);
      if (eligible.count(it->key)) {
        if (!it->visited) {
          d.hand = next == d.queue.end() ? "" : next->key;
          return it->key;
        }
        it->visited = false;
      }
      it = next == d.queue.end() ? std::prev(d.queue.end()) : next;
    }
    return {};
  }
  void Removed(int domain, const std::string& key) {
    std::lock_guard<std::mutex> lock(mu_);
    auto& d = domains_[domain];
    auto found = d.index.find(key);
    if (found == d.index.end()) return;
    if (d.hand == key)
      d.hand = found->second == d.queue.begin() ? "" : std::prev(found->second)->key;
    d.queue.erase(found->second);
    d.index.erase(found);
  }
 private:
  struct Entry { std::string key; bool visited; };
  struct Domain {
    std::list<Entry> queue;
    std::unordered_map<std::string, std::list<Entry>::iterator> index;
    std::string hand;
  };
  std::mutex mu_;
  std::unordered_map<int, Domain> domains_;
};
}  // namespace tokenfs_policy
