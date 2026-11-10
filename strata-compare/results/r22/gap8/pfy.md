reference: /home/USER/ai-speed-testing/strata-compare/results/r22/gap8/pfy/ref
run                                   prompts   n   top-1   KL mean KL median    KL max
ref2                                      all  40  100.0%  0.000000  0.000000  0.000000
ref2                            long (2K-32K)  40  100.0%  0.000000  0.000000  0.000000
ref2                                    2K-8K  15  100.0%  0.000000  0.000000  0.000000
ref2                                   8K-16K  11  100.0%  0.000000  0.000000  0.000000
ref2                                  16K-32K  14  100.0%  0.000000  0.000000  0.000000
                             worst: 32k-2048 0.00000, 32k-4096 0.00000, 32k-6144 0.00000
unfused                                   all  40   87.5%  0.161958  0.011031  2.464120
unfused                         long (2K-32K)  40   87.5%  0.161958  0.011031  2.464120
unfused                                 2K-8K  15   86.7%  0.200961  0.011031  2.464120
unfused                                8K-16K  11   81.8%  0.177575  0.030704  1.045941
unfused                               16K-32K  14   92.9%  0.107898  0.004419  1.018085
                             worst: ldrsyn20k-7680 2.46412 (top-1 differs), ldrsyn20k-9728 1.04594 (top-1 differs), 32k-28672 1.01809
cpushare                                  all  40   87.5%  0.364874  0.011573  9.761489
cpushare                        long (2K-32K)  40   87.5%  0.364874  0.011573  9.761489
cpushare                                2K-8K  15   86.7%  0.159451  0.011573  1.859181
cpushare                               8K-16K  11   81.8%  0.165506  0.017832  1.512813
cpushare                              16K-32K  14   92.9%  0.741615  0.003785  9.761489
                             worst: tf-long28k-21504 9.76149 (top-1 differs), ldrsyn20k-7680 1.85918 (top-1 differs), ldrsyn20k-9728 1.51281 (top-1 differs)
v2                                        all  40   90.0%  0.181292  0.015066  3.132749
v2                              long (2K-32K)  40   90.0%  0.181292  0.015066  3.132749
v2                                      2K-8K  15   93.3%  0.254142  0.008591  3.132749
v2                                     8K-16K  11   81.8%  0.166945  0.015066  1.071550
v2                                    16K-32K  14   92.9%  0.114512  0.015288  0.971364
                             worst: ldrsyn20k-7680 3.13275 (top-1 differs), ldrsyn20k-9728 1.07155 (top-1 differs), 32k-28672 0.97136
v2d                                       all  40   90.0%  0.402121  0.011609  7.834521
v2d                             long (2K-32K)  40   90.0%  0.402121  0.011609  7.834521
v2d                                     2K-8K  15  100.0%  0.099088  0.022458  0.493331
v2d                                    8K-16K  11   81.8%  0.372015  0.011609  2.710329
v2d                                   16K-32K  14   85.7%  0.750454  0.008906  7.834521
                             worst: tf-long28k-21504 7.83452 (top-1 differs), 32k-12288 2.71033 (top-1 differs), 32k-28672 2.14755 (top-1 differs)
v2g                                       all  40   82.5%  0.384769  0.020283  9.294161
v2g                             long (2K-32K)  40   82.5%  0.384769  0.020283  9.294161
v2g                                     2K-8K  15   80.0%  0.701012  0.021024  9.294161
v2g                                    8K-16K  11   81.8%  0.220181  0.023336  1.710214
v2g                                   16K-32K  14   85.7%  0.175256  0.017837  1.100247
                             worst: ldrsyn20k-7680 9.29416 (top-1 differs), 32k-12288 1.71021 (top-1 differs), tf-long28k-21504 1.10025 (top-1 differs)
reference: /home/USER/ai-speed-testing/strata-compare/results/r22/gap8/pfy/refi8
run                                   prompts   n   top-1   KL mean KL median    KL max
unfusedi8                                 all  40   85.0%  0.187476  0.010683  1.917393
unfusedi8                       long (2K-32K)  40   85.0%  0.187476  0.010683  1.917393
unfusedi8                               2K-8K  15  100.0%  0.120062  0.006248  1.000053
unfusedi8                              8K-16K  11   72.7%  0.300443  0.023587  1.170564
unfusedi8                             16K-32K  14   78.6%  0.170944  0.006684  1.917393
                             worst: tf-long28k-21504 1.91739 (top-1 differs), ldrsyn20k-9728 1.17056 (top-1 differs), 32k-12288 1.14266 (top-1 differs)
cpusharei8                                all  40   92.5%  0.306680  0.014908  9.018596
cpusharei8                      long (2K-32K)  40   92.5%  0.306680  0.014908  9.018596
cpusharei8                              2K-8K  15   93.3%  0.661812  0.013330  9.018596
cpusharei8                             8K-16K  11   90.9%  0.110535  0.022020  0.806816
cpusharei8                            16K-32K  14   92.9%  0.080296  0.016319  0.432667
                             worst: ldrsyn20k-7680 9.01860 (top-1 differs), ldrsyn20k-9728 0.80682 (top-1 differs), tf-long28k-2560 0.59195
immai8                                    all  40   80.0%  0.116229  0.017908  1.100080
immai8                          long (2K-32K)  40   80.0%  0.116229  0.017908  1.100080
immai8                                  2K-8K  15   86.7%  0.144856  0.016767  1.100080
immai8                                 8K-16K  11   72.7%  0.123296  0.044097  0.585004
immai8                                16K-32K  14   78.6%  0.080006  0.011004  0.463977
                             worst: ldrsyn20k-7680 1.10008 (top-1 differs), tf-long40k-3072 0.62728, ldrsyn20k-9728 0.58500 (top-1 differs)
