#include "../src/read_fill.h"
#include <cassert>
#include <filesystem>
#include <fstream>
#include <fcntl.h>
int main(){
  auto root=std::filesystem::temp_directory_path()/("tokenfs-fill-test-"+std::to_string(getpid()));
  std::filesystem::create_directory(root);auto path=root/"source";
  std::ofstream(path)<<"abcdefgh";int fd=open(path.c_str(),O_RDONLY);assert(fd>=0);
  ReadFillPool pool(8);auto b=pool.Acquire("a",fd,8);assert(b && pool.UsedBytes()==8);
  assert(!pool.Acquire("b",fd,8) && !pool.Acquire("a",fd,8));
  assert(!b->Append(0,"abcd",4,fd) && !b->Dispatched());
  assert(!pool.FindComplete("a",path.string(),8));
  assert(!b->VerifyFileBytes(path.string()));
  assert(b->Append(4,"efgh",4,fd) && b->Matches(path.string(),8));
  assert(!b->Append(8,"",0,fd));
  assert(std::string(b->Data().begin(),b->Data().end())=="abcdefgh");
  assert(b->Checksum()=="fnv1a64:25da8c1836a8d66d");
  auto candidate=root/"candidate";
  assert(!b->VerifyFileBytes(candidate.string()));
  std::ofstream(candidate)<<"abcdefgh";assert(b->VerifyFileBytes(candidate.string()));
  std::ofstream(candidate)<<"abcdEfgh";assert(!b->VerifyFileBytes(candidate.string()));
  std::ofstream(candidate)<<"abcdefg";assert(!b->VerifyFileBytes(candidate.string()));
  std::ofstream(candidate)<<"abcdefghx";assert(!b->VerifyFileBytes(candidate.string()));
  assert(!b->VerifyFileBytes(root.string()));
  auto borrowed=pool.FindComplete("a",path.string(),8);assert(borrowed==b);
  char bytes[12]{};assert(borrowed->ReadCaptured(fd,bytes,12,0)==8 && std::string(bytes,8)=="abcdefgh");
  assert(borrowed->ReadCaptured(fd,bytes,3,2)==3 && std::string(bytes,3)=="cde");
  assert(borrowed->ReadCaptured(fd,bytes,8,8)==0 && borrowed->ReadCaptured(fd,bytes,8,-1)==-EINVAL);
  b.reset();assert(pool.UsedBytes()==8 && !pool.Acquire("b",fd,8));
  borrowed.reset();assert(pool.UsedBytes()==0 && pool.PeakBytes()==8);
  assert(!pool.FindComplete("a",path.string(),8));
  b=pool.Acquire("a",fd,8);assert(b);
  assert(!b->Append(4,"efgh",4,fd) && !b->Append(0,"abcdefgh",8,fd) && !b->Dispatched());
  b.reset();b=pool.Acquire("a",fd,8);
  assert(!b->Append(0,"abcdefghijkl",12,fd));b.reset();
  b=pool.Acquire("a",fd,8);assert(b->Append(0,"abcdefgh",8,fd));
  std::ofstream(root/"replacement")<<"abcdefgh";
  std::filesystem::rename(root/"replacement",path);
  assert(!b->Matches(path.string(),8));
  assert(!pool.FindComplete("a",path.string(),8));
  int replaced=open(path.c_str(),O_RDONLY);assert(!b->MatchesFd(replaced));
  assert(b->ReadCaptured(replaced,bytes,8,0)==-ESTALE);close(replaced);b.reset();
  assert(!pool.Acquire("large",fd,9));
  close(fd);fd=open(path.c_str(),O_RDONLY);assert(fd>=0);
  {
    const auto large_path=root/"multi-chunk";std::string payload(150003,'\0');
    for(size_t i=0;i<payload.size();++i)payload[i]=char((i*37)%256);
    std::ofstream(large_path,std::ios::binary).write(payload.data(),payload.size());
    int large_fd=open(large_path.c_str(),O_RDONLY);assert(large_fd>=0);
    ReadFillPool large_pool(payload.size());auto large=large_pool.Acquire("large",large_fd,payload.size());
    assert(large && large->Append(0,payload.data(),payload.size(),large_fd));
    assert(large->VerifyFileBytes(large_path.string()));
    payload[65536]^=1;
    std::ofstream(candidate,std::ios::binary).write(payload.data(),payload.size());
    assert(!large->VerifyFileBytes(candidate.string()));close(large_fd);
  }
  std::weak_ptr<ReadFillPool::Buffer> lifetime;
  {
    ReadFillPool retained(16,true);
    auto capture=[&](const char* key){auto x=retained.Acquire(key,fd,8);assert(x);assert(x->Append(0,"abcdefgh",8,fd));retained.Retain(x);return x;};
    auto a=capture("a"),c=capture("b");a.reset();c.reset();
    assert(retained.UsedBytes()==16);
    a=retained.FindComplete("a",path.string(),8);assert(a);a.reset();
    c=capture("c");assert(!retained.FindComplete("b",path.string(),8));
    a=retained.FindComplete("a",path.string(),8);assert(a);
    assert(!retained.Acquire("d",fd,8)); // two live reader/copy pins, no overcommit
    a.reset();auto d=capture("d");assert(!retained.FindComplete("a",path.string(),8));
    assert(retained.UsedBytes()==16 && retained.PeakBytes()==16);
    c.reset();d.reset();lifetime=retained.FindComplete("d",path.string(),8);
    std::ofstream(root/"changed")<<"ijklmnop";std::filesystem::rename(root/"changed",path);
    assert(!retained.FindComplete("c",path.string(),8));
    assert(retained.UsedBytes()==8); // invalid retained bytes can be reclaimed
  }
  assert(lifetime.expired()); // no Buffer -> Budget -> Buffer ownership cycle
  close(fd);
  std::ofstream(root/"canonical")<<"abcdefgh";std::ofstream(root/"replica")<<"abcdefgh";
  fd=open((root/"replica").c_str(),O_RDONLY);int canonical=open((root/"canonical").c_str(),O_RDONLY);
  {
    ReadFillPool anchored(8,true);auto x=anchored.Acquire("k",fd,8,(root/"canonical").string());assert(x);
    assert(x->Append(0,"abcdefgh",8,fd));anchored.Retain(x);
    std::filesystem::remove(root/"replica"); // evicting the disk copy cannot revoke valid immutable bytes
    assert(x->ReadCaptured(canonical,bytes,8,0)==8 && std::string(bytes,8)=="abcdefgh");
    assert(x->Matches((root/"canonical").string(),8));
    std::ofstream(root/"canonical2")<<"ijklmnop";std::filesystem::rename(root/"canonical2",root/"canonical");
    assert(!anchored.FindComplete("k",(root/"canonical").string(),8));
    int changed=open((root/"canonical").c_str(),O_RDONLY);assert(x->ReadCaptured(changed,bytes,8,0)==-ESTALE);close(changed);
  }
  close(fd);close(canonical);std::filesystem::remove_all(root);
}
