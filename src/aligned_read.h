#pragma once
#include <algorithm>
#include <array>
#include <cerrno>
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <limits>
#include <mutex>
#include <sys/stat.h>
#include <unistd.h>

// Per-open reuse of bytes already fetched by O_DIRECT alignment. This is not
// read-ahead: a read never requests more backend bytes than the original
// aligned bounce-buffer path. The at-most-one-page suffix is accounted
// separately from retained captures and dies with the handle.
class AlignedReadTail {
  friend struct AlignedReadTailTestAccess;
 public:
  static constexpr size_t kAlignment=4096;
  struct Stats {
    uint64_t pread_ops=0,pread_bytes=0,pread_ns=0,tail_hits=0,tail_bytes=0,invalidations=0;
  };
  ssize_t Read(int fd,char* output,size_t size,off_t offset,Stats& stats,bool profile=false) {
    return ReadImpl(fd,output,size,offset,stats,profile,
      [](int source,void* data,size_t count,off_t at){return pread(source,data,count,at);});
  }
  size_t RetainedBytes() const {std::lock_guard<std::mutex> lock(mu_);return tail_size_;}
 private:
  template<class BackendRead>
  ssize_t ReadImpl(int fd,char* output,size_t size,off_t offset,Stats& stats,bool profile,BackendRead backend_read) {
    stats={};std::lock_guard<std::mutex> lock(mu_);
    if(offset<0 || size>size_t(std::numeric_limits<ssize_t>::max())) {
      errno=EINVAL;return -1;
    }
    if(!size)return 0;
    if(tail_size_) {
      struct stat current{};
      // Reuse only the next contiguous, fully covered request. Partial or
      // overlapping requests use the unchanged aligned backend operation.
      if(offset==tail_offset_ && size<=tail_.size() && tail_size_<=tail_.size() && size<=tail_size_ &&
         fstat(fd,&current)==0 && SameIdentity(current,identity_)) {
        std::memcpy(output,tail_.data(),size);
        tail_size_-=size;tail_offset_+=off_t(size);
        if(tail_size_)std::memmove(tail_.data(),tail_.data()+size,tail_size_);
        stats.tail_hits=1;stats.tail_bytes=size;return ssize_t(size);
      }
      stats.invalidations=1;tail_size_=0;
    }
    const off_t aligned_offset=offset/off_t(kAlignment)*off_t(kAlignment);
    const size_t skip=size_t(offset-aligned_offset);
    if(size>size_t(std::numeric_limits<ssize_t>::max())-skip-(kAlignment-1)) {
      errno=EINVAL;return -1;
    }
    const size_t aligned_size=(size+skip+kAlignment-1)/kAlignment*kAlignment;
    if(uint64_t(aligned_offset)>uint64_t(std::numeric_limits<off_t>::max())-aligned_size) {
      errno=EINVAL;return -1;
    }
    void* bounce=nullptr;
    if(posix_memalign(&bounce,kAlignment,aligned_size)!=0){errno=ENOMEM;return -1;}
    struct stat before{};
    // Exactly aligned requests cannot leave a suffix. Otherwise remember the
    // identity BEFORE pread: use-time validation also rejects mutations that
    // happen during pread, without a redundant post-read metadata operation.
    const bool identified=aligned_size>skip+size && fstat(fd,&before)==0 && S_ISREG(before.st_mode);
    const auto start=profile?NowNs():0;
    const ssize_t fetched=backend_read(fd,bounce,aligned_size,aligned_offset);
    const int saved_errno=errno;
    stats.pread_ops=1;
    if(profile)stats.pread_ns=NowNs()-start;
    if(fetched>0)stats.pread_bytes=uint64_t(fetched);
    ssize_t result=fetched;
    if(fetched>=0) {
      result=fetched<=ssize_t(skip)?0:std::min<ssize_t>(size,fetched-ssize_t(skip));
      if(result)std::memcpy(output,static_cast<char*>(bounce)+skip,size_t(result));
      const size_t consumed=skip+size_t(result);
      const size_t extra=size_t(fetched)>consumed?size_t(fetched)-consumed:0;
      if(extra && extra<kAlignment && identified) {
        std::memcpy(tail_.data(),static_cast<char*>(bounce)+consumed,extra);
        tail_offset_=offset+result;tail_size_=extra;identity_=before;
      }
    }
    free(bounce);errno=saved_errno;return result;
  }
  static uint64_t NowNs() {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(
      std::chrono::steady_clock::now().time_since_epoch()).count();
  }
  static bool SameIdentity(const struct stat& a,const struct stat& b) {
    if(a.st_dev!=b.st_dev || a.st_ino!=b.st_ino || a.st_size!=b.st_size)return false;
#ifdef __APPLE__
    return a.st_mtimespec.tv_sec==b.st_mtimespec.tv_sec && a.st_mtimespec.tv_nsec==b.st_mtimespec.tv_nsec &&
      a.st_ctimespec.tv_sec==b.st_ctimespec.tv_sec && a.st_ctimespec.tv_nsec==b.st_ctimespec.tv_nsec;
#else
    return a.st_mtim.tv_sec==b.st_mtim.tv_sec && a.st_mtim.tv_nsec==b.st_mtim.tv_nsec &&
      a.st_ctim.tv_sec==b.st_ctim.tv_sec && a.st_ctim.tv_nsec==b.st_ctim.tv_nsec;
#endif
  }
  mutable std::mutex mu_;
  std::array<char,kAlignment> tail_{};
  size_t tail_size_=0;off_t tail_offset_=0;struct stat identity_{};
};
