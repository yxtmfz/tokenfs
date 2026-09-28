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
  assert(b->Append(4,"efgh",4,fd) && b->Matches(path.string(),8));
  assert(!b->Append(8,"",0,fd));
  assert(std::string(b->Data().begin(),b->Data().end())=="abcdefgh");
  assert(b->Checksum()=="fnv1a64:25da8c1836a8d66d");
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
  close(fd);std::filesystem::remove_all(root);
}
