# nchnroutes-ng

This is an enhanced version of nchnroutes, which adds the ability to specify a particular country or a specific subnet to a designated route, in addition to generating a non-mainland China IP list.

Requires Python 3, no additional dependencies.

```
$ python3 produce.py -h

usage: produce.py [-h] [--exclude [CIDR [CIDR ...]]] [--next INTERFACE OR IP]
                  [--ipv4-list [{apnic,ipip} [{apnic,ipip} ...]]]
                  [--country-exit [COUNTRY:INTERFACE]]
                  [--custom-exit [CIDR:INTERFACE]]

Generate non-China routes for BIRD.

optional arguments:
  -h, --help            show this help message and exit
  --exclude [CIDR [CIDR ...]]
                        IPv4 ranges to exclude in CIDR format
  --next INTERFACE OR IP
                        next hop for where non-China IP address, this is
                        usually the tunnel interface
  --ipv4-list [{apnic,ipip} [{apnic,ipip} ...]]
                        IPv4 lists to use when subtracting China based IP,
                        multiple lists can be used at the same time (default:
                        apnic ipip)
  --country-exit [COUNTRY:INTERFACE]
                        Mapping between country codes and exit interfaces, 
                        e.g., US:eth0 CN:eth1
  --custom-exit [CIDR:INTERFACE]
                        Custom IPv4/IPv6 ranges with specific exit interfaces,
                         e.g., 192.168.10.0/24:eth2 10.0.0.0/8:eth3 2001:db8::/32:eth4
```

To specify China IPv4 list to use, use the `--ipv4-list` as the following:

* `python3 produce.py --ipv4-list ipip` - only use list [from ipip.net](https://github.com/17mon/china_ip_list)
* `python3 produce.py --ipv4-list apnic` - only use list [from APNIC](https://ftp.apnic.net/stats/apnic/delegated-apnic-latest)
* `python3 produce.py --ipv4-list apnic ipip` - use both lists **(default)**

If you want to run this automatically, you can first edit `Makefile` and uncomment the BIRD reload code
at the end, then:

```
sudo crontab -e
```

and add `0 0 * * 0 make -C /path/to/nchnroutes` to the file.

This will re generate the table every Sunday at midnight and reload BIRD afterwards.
