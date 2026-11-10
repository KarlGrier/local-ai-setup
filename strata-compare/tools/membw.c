// membw.c - read bandwidth (STREAM-like "sum" kernel) for N threads over a large buffer, per-CPU pinned.
// usage: membw <GiB> <cpu-list e.g. 0-15 or 0-7,16-23> [reps]
#define _GNU_SOURCE
#include <immintrin.h>
#include <pthread.h>
#include <sched.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
static double now(){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec+t.tv_nsec*1e-9;}
typedef struct{int cpu;char*p;size_t n;double sum;pthread_barrier_t*b;int reps;double t0,t1;}A;
static void* run(void*v){A*a=v;cpu_set_t s;CPU_ZERO(&s);CPU_SET(a->cpu,&s);pthread_setaffinity_np(pthread_self(),sizeof s,&s);
 memset(a->p,1,a->n); pthread_barrier_wait(a->b); __m512i acc=_mm512_setzero_si512();
 double t0=now(); for(int r=0;r<a->reps;r++) for(size_t i=0;i<a->n;i+=256){
  acc=_mm512_add_epi64(acc,_mm512_load_si512(a->p+i)); acc=_mm512_add_epi64(acc,_mm512_load_si512(a->p+i+64));
  acc=_mm512_add_epi64(acc,_mm512_load_si512(a->p+i+128)); acc=_mm512_add_epi64(acc,_mm512_load_si512(a->p+i+192));}
 a->t0=t0; a->t1=now(); a->sum=(double)_mm512_reduce_add_epi64(acc); return 0;}
int main(int c,char**v){ double gib=atof(v[1]); int cpus[256],n=0; char*s=strdup(v[2]),*tok=strtok(s,",");
 while(tok){int a,b; if(sscanf(tok,"%d-%d",&a,&b)==2){for(int i=a;i<=b;i++)cpus[n++]=i;}else cpus[n++]=atoi(tok); tok=strtok(0,",");}
 int reps=c>3?atoi(v[3]):3; size_t per=((size_t)(gib*(1ull<<30))/n)&~(size_t)4095; pthread_barrier_t b; pthread_barrier_init(&b,0,n);
 A*a=calloc(n,sizeof(A)); pthread_t*t=calloc(n,sizeof(pthread_t));
 for(int i=0;i<n;i++){a[i].cpu=cpus[i];a[i].n=per;a[i].b=&b;a[i].reps=reps;a[i].p=aligned_alloc(4096,per);pthread_create(&t[i],0,run,&a[i]);}
 double t0=1e18,t1=0,sum=0; for(int i=0;i<n;i++){pthread_join(t[i],0); if(a[i].t0<t0)t0=a[i].t0; if(a[i].t1>t1)t1=a[i].t1; sum+=a[i].sum;}
 printf("threads %d  cpus %s  %.1f GiB x %d reps: %.1f GB/s (chk %.0f)\n",n,v[2],gib,reps,(double)per*n*reps/(t1-t0)/1e9,sum); return 0;}
