#pragma once
#include <cstdint>
#include <mutex>
#include <optional>

// A small FUSE tail carries fixed call/alignment overhead. Averaging its us/byte
// equally with a MiB chunk can reverse the tier ordering. Aggregate actual bytes
// and durations before emitting ONE rate per logical open, without discarding tails.
class RequestReadCost {
 public:
  struct Sample {uint64_t bytes=0,micros=0;};
  explicit RequestReadCost(uint64_t expected):expected_(expected){}
  std::optional<Sample> Add(int64_t offset,uint64_t bytes,uint64_t micros) {
    std::lock_guard<std::mutex> lock(mu_);
    if(emitted_)return {};
    if(offset<0 || uint64_t(offset)!=next_)sequential_=false;
    next_=offset<0?0:uint64_t(offset)+bytes;
    total_.bytes+=bytes;total_.micros+=micros;
    if(sequential_ && expected_ && total_.bytes==expected_)return Take();
    return {};
  }
  std::optional<Sample> Finish(){std::lock_guard<std::mutex> lock(mu_);return Take();}
 private:
  std::optional<Sample> Take(){
    if(emitted_)return {};
    emitted_=true;
    return total_.bytes?std::optional<Sample>(total_):std::nullopt;
  }
  std::mutex mu_;uint64_t expected_,next_=0;bool sequential_=true,emitted_=false;Sample total_;
};
