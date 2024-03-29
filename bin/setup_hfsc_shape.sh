#!/bin/bash
# Source: https://gist.github.com/eqhmcow/939373

# As the "bufferbloat" folks have recently re-discovered and/or more widely
# publicized, congestion avoidance algorithms (such as those found in TCP) do
# a great job of allowing network endpoints to negotiate transfer rates that
# maximize a link's bandwidth usage without unduly penalizing any particular
# stream. This allows bulk transfer streams to use the maximum available
# bandwidth without affecting the latency of non-bulk (e.g. interactive)
# streams.

# In other words, TCP lets you have your cake and eat it too -- both fast
# downloads and low latency all at the same time.

# However, this only works if TCP's afore-mentioned congestion avoidance
# algorithms actually kick in. The most reliable method of signaling
# congestion is to drop packets. (There are other ways, such as ECN, but
# unfortunately they're still not in wide use.)

# Dropping packets to make the network work better is kinda counter-intuitive.
# But, that's how TCP works. And if you take advantage of that, you can make
# TCP work great.

# Dropping packets gets TCP's attention and fast. The sending endpoint
# throttles back to avoid further network congestion. In other words, your
# fast download slows down. Then, as long as there's no further congestion,
# the sending endpoint gradually increases the transfer rate. Then the cycle
# repeats. It can get a lot more complex than that simple explanation, but the
# main point is: dropping packets when there's congestion is good.

# Traffic shaping is all about slowing down and/or dropping (or ECN marking)
# packets. The thing is, it's much better for latency to simply drop packets
# than it is to slow them down. Linux has a couple of traffic shapers that
# aren't afraid to drop packets. One of the most well-known is TBF, the Token
# Bucket Filter. Normally it slows down packets to a specific rate. But, it
# also accepts a "limit" option to specify the maximum number of packets to
# queue. When the limit is exceeded, packets are dropped.

# TBF's simple "tail-drop" algorithm is actually one of the worst kinds of
# "active queue management" (AQM) that you can do. But even still, it can make
# a huge difference. Applying TBF alone (with a short enough limit) can make a
# maddeningly high-latency link usable again in short order.

# TBF's big disadvantage is that it's a "classless" shaper. That means you
# can't prioritize one TCP stream over another. That's where HTB, the
# Hierarchical Token Bucket, comes in. HTB uses the same general algorithm as
# TBF while also allowing you to filter specific traffic to prioritized queues.

# But HTB has a big weakness: it doesn't have a good, easy way of specifying a
# queue limit like TBF does. That means, compared to TBF, HTB is much more
# inclined to slow packets rather than to drop them. That hurts latency, bad.

# So now we come to Linux traffic shaping's best kept secret: the HFSC shaper.
# HFSC stands for Hierarchical Fair Service Curve. The linux implementation is
# a complex beast, enough so to have a 9 part question about it on serverfault
# ( http://serverfault.com/questions/105014/does-anyone-really-understand-how-hfsc-scheduling-in-linux-bsd-works ).
# Nonetheless, HFSC can be understood in a simplified way as HTB with limits.
# HFSC allows you to classify traffic (like HTB, unlike TBF), but it also has
# no fear of dropping packets (unlike HTB, like TBF).

# HFSC does a great job of keeping latency low. With it, it's possible to fully
# saturate a link while maintaining perfect non-bulk session interactivity.
# It is the holy grail of traffic shaping, and it's in the stock kernel.

# To get the best results, HFSC should be combined with SFQ (Stochastic
# Fairness Queueing) and optionally an ingress filter. If all three are used,
# it's possible to maintain low-latency interactive sessions even without any
# traffic prioritization. Further adding prioritization then maximizes
# interactivity.

# Here's how it's done:

# set this to your internet-facing network interface:
WAN_INTERFACE=wlan0

# set this to your local network interface:
LAN_INTERFACE=eth0
LAN_NETWORK=10.42.0.1/24

# how fast is your downlink?
MAX_DOWNRATE=30mbit

# how close should we get to max down? e.g. 95%
USE_DOWNPERCENT=0.90

# how fast is your uplink?
MAX_UPRATE=30mbit

# how close should we get to max up? e.g. 90%
USE_UPPERCENT=0.90

# what port do you want to prioritize? e.g. for ssh, use 22
# 3074 for xbox
INTERACTIVE_PORT=3074
# NOTE: port 22 is prioritized as well, see below for the full list of
# prioritized ports. (this script has been updated to use some loops to make
# adding / removing ports easier, and I've added a number of xbox-related
# ports.)

## now for the magic
# set this to the path to your tc binary
#TC=/usr/sbin/tc
TC=/sbin/tc

# remove any existing qdiscs
# this lets you re-run this script as much as you want to try different
# settings, we're always starting fresh
$TC qdisc del dev $WAN_INTERFACE root 2> /dev/null
$TC qdisc del dev $WAN_INTERFACE ingress 2> /dev/null
$TC qdisc del dev $LAN_INTERFACE root 2> /dev/null
$TC qdisc del dev $LAN_INTERFACE ingress 2> /dev/null

# computations
MAX_UPNUM=`echo $MAX_UPRATE | sed 's/[^0-9]//g'`
MAX_UPBASE=`echo $MAX_UPRATE | sed 's/[0-9]//g'`
MAX_DOWNNUM=`echo $MAX_DOWNRATE | sed 's/[^0-9]//g'`
MAX_DOWNBASE=`echo $MAX_DOWNRATE | sed 's/[0-9]//g'`

NEAR_MAX_UPNUM=`echo "$MAX_UPNUM * $USE_UPPERCENT" | bc | xargs printf "%.0f"`
NEAR_MAX_UPRATE="${NEAR_MAX_UPNUM}${MAX_UPBASE}"

NEAR_MAX_DOWNNUM=`echo "$MAX_DOWNNUM * $USE_DOWNPERCENT" | bc | xargs printf "%.0f"`
NEAR_MAX_DOWNRATE="${NEAR_MAX_DOWNNUM}${MAX_DOWNBASE}"

HALF_MAXUPNUM=$(( $MAX_UPNUM / 2 ))
HALF_MAXUP="${HALF_MAXUPNUM}${MAX_UPBASE}"

HALF_MAXDOWNNUM=$(( $MAX_DOWNNUM / 2 ))
HALF_MAXDOWN="${HALF_MAXDOWNNUM}${MAX_DOWNBASE}"

## mark small packets - i.e. ACKs
## (run this once and/or add it to your regular IP tables rules) -- this iptables command
# only needs to run once per reboot, whereas the rest of this script can be run as often
# as you like to try different settings (the qdiscs are cleared / reset at the top of the script)
#/usr/sbin/iptables -t mangle -A PREROUTING -p tcp -m length --length 0:128 -j MARK --set-mark 2

# install HFSC under WAN to limit upload
$TC qdisc add dev $WAN_INTERFACE root handle 1: hfsc default 11
$TC class add dev $WAN_INTERFACE parent 1: classid 1:1 hfsc sc rate $NEAR_MAX_UPRATE ul rate $NEAR_MAX_UPRATE
$TC class add dev $WAN_INTERFACE parent 1:1 classid 1:10 hfsc sc umax 1540 dmax 5ms rate $HALF_MAXUP ul rate $NEAR_MAX_UPRATE
$TC class add dev $WAN_INTERFACE parent 1:1 classid 1:11 hfsc sc umax 1540 dmax 5ms rate $HALF_MAXUP ul rate $HALF_MAXUP
#$TC class add dev $WAN_INTERFACE parent 1:1 classid 1:11 hfsc sc umax 1540 dmax 5ms rate $HALF_MAXUP ul rate $NEAR_MAX_UPRATE

# install ingress filter to limit download to 97% max
MAX_DOWNRATE_INGRESSNUM=`echo "$MAX_DOWNNUM * 0.97" | bc | xargs printf "%.0f"`
MAX_DOWNRATE_INGRESS="${MAX_DOWNRATE_INGRESSNUM}${MAX_DOWNBASE}"
$TC qdisc add dev $WAN_INTERFACE handle ffff: ingress
# NOTE: we route all prioritized traffic through the ingress filter with NO policing;
# that is, we do not police-limit prioritized traffic.

# prioritize interactive port blocks: xbox gaming
for i in $INTERACTIVE_PORT 30000 31000 32000 33000 34000 35000 36000 37000 38000 39000 40000 41000; do
# recent xbox games enjoy using high ports -- the same port numbers which
# client OSes occasionally also use for source ports for bulk traffic (e.g.
# http for streaming) -- so, don't prioritize high source ports, only high
# dest ports (that is, only prioritize streams connecting to ports the gaming
# servers are listening on)
#  $TC filter add dev $WAN_INTERFACE protocol ip parent 1:0 prio 1 u32 match ip sport $i 0xfc00 flowid 1:10
  $TC filter add dev $WAN_INTERFACE protocol ip parent 1:0 prio 1 u32 match ip dport $i 0xfc00 flowid 1:10
# policer:
#  $TC filter add dev $WAN_INTERFACE parent ffff: protocol ip prio 1 u32 match ip sport $i 0xfc00 flowid :1
  $TC filter add dev $WAN_INTERFACE parent ffff: protocol ip prio 1 u32 match ip dport $i 0xfc00 flowid :1
done
# do prioritize low xbox source port, some games still use this port range for a source port
# (in that case it doesn't matter which port they listen on; the client connects
# from the low source port to any server-side port)
$TC filter add dev $WAN_INTERFACE protocol ip parent 1:0 prio 1 u32 match ip sport $INTERACTIVE_PORT 0xfc00 flowid 1:10
# policer:
$TC filter add dev $WAN_INTERFACE parent ffff: protocol ip prio 1 u32 match ip sport $INTERACTIVE_PORT 0xfc00 flowid :1

# prioritize additional single ports: ssh, VPN, webex, google hangouts
# audio / video. VPN port (4500) may also be used for AT&T / t-mobile phone
# calls over wifi, and Apple Facetime uses ports around 3xxx, which are already
# prioritized for xbox. in fact it's probably safe to prioritize any low
# source AND dest ports (lower than 20,000) other than 80 and 443 (but we
# don't do that here)
for i in 22 4500 9000 19302 19303 19304 19305 19306 19307 19308 19309; do
  $TC filter add dev $WAN_INTERFACE protocol ip parent 1:0 prio 1 u32 match ip sport $i 0xffff flowid 1:10
  $TC filter add dev $WAN_INTERFACE protocol ip parent 1:0 prio 1 u32 match ip dport $i 0xffff flowid 1:10
# policer:
  $TC filter add dev $WAN_INTERFACE parent ffff: protocol ip prio 1 u32 match ip sport $i 0xffff flowid :1
  $TC filter add dev $WAN_INTERFACE parent ffff: protocol ip prio 1 u32 match ip dport $i 0xffff flowid :1
done

# also VPN IP range - set this if you know your corporate VPN IP range
#$TC filter add dev $WAN_INTERFACE protocol ip parent 1:0 prio 1 u32 match ip src 1.2.3.4/24 flowid 1:10
#$TC filter add dev $WAN_INTERFACE protocol ip parent 1:0 prio 1 u32 match ip dst 1.2.3.4/24 flowid 1:10
# policer:
#$TC filter add dev $WAN_INTERFACE parent ffff: protocol ip prio 1 u32 match ip src 1.2.3.4/24 flowid :1
#$TC filter add dev $WAN_INTERFACE parent ffff: protocol ip prio 1 u32 match ip dst 1.2.3.4/24 flowid :1

# also icmp
$TC filter add dev $WAN_INTERFACE protocol ip parent 1:0 prio 1 u32 match ip protocol 1 0xff flowid 1:10
# policer:
$TC filter add dev $WAN_INTERFACE parent ffff: protocol ip prio 1 u32 match ip protocol 1 0xff flowid :1

# prioritize ack (iptables-marked packets)
$TC filter add dev $WAN_INTERFACE protocol ip parent 1:0 prio 2 handle 2 fw flowid 1:10
# policer:
$TC filter add dev $WAN_INTERFACE parent ffff: protocol ip prio 2 handle 2 fw flowid :1

# add SFQ (or fq_codel if you have at least kernel 3.16 or so)
# (or any anti-bufferbloat qdisc such as cake, if you have an ever newer kernel)

# NOTE:
# I tried running without hfsc, and only using fq_codel -- it doesn't work as well
# as running with both hfsc and SFQ. that is, xbox gaming latency went to hell cuz
# fq_codel didn't know when to start dropping packets. however, once you have hfsc
# in the mix any FQ-like qdisc should work here.

# UPDATE:
# I recommend using SFQ *instead* of fq_codel, at least on slow / 32-bit / embedded
# systems. In my anecdotal testing, fq_codel can slow down streams more than SFQ
# does, and introduce a bit of latency.

$TC qdisc add dev $WAN_INTERFACE parent 1:10 handle 30: sfq perturb 10
$TC qdisc add dev $WAN_INTERFACE parent 1:11 handle 40: sfq perturb 10
#$TC qdisc add dev $WAN_INTERFACE parent 1:10 handle 30: fq_codel
#$TC qdisc add dev $WAN_INTERFACE parent 1:11 handle 40: fq_codel

# enact policer for all other traffic
$TC filter add dev $WAN_INTERFACE parent ffff: protocol ip prio 50 u32 match ip src 0.0.0.0/0 police rate $MAX_DOWNRATE_INGRESS burst 20k drop flowid :2


# install HFSC under LAN to limit download
$TC qdisc add dev $LAN_INTERFACE root handle 1: hfsc default 11
$TC class add dev $LAN_INTERFACE parent 1: classid 1:1 hfsc sc rate 1000mbit ul rate 1000mbit
$TC class add dev $LAN_INTERFACE parent 1:1 classid 1:10 hfsc sc umax 1540 dmax 5ms rate 900mbit ul rate 900mbit
$TC class add dev $LAN_INTERFACE parent 1:1 classid 1:11 hfsc sc umax 1540 dmax 5ms rate $HALF_MAXDOWN ul rate $NEAR_MAX_DOWNRATE

# prioritize local LAN traffic
$TC filter add dev $LAN_INTERFACE protocol ip parent 1:0 prio 1 u32 match ip src $LAN_NETWORK match ip dst $LAN_NETWORK flowid 1:10

# prioritize interactive port blocks: xbox gaming
# see above for why we only prioritize the source port and not the dest port here
# (in this case source port is remote host's port)
for i in $INTERACTIVE_PORT 30000 31000 32000 33000 34000 35000 36000 37000 38000 39000 40000 41000; do
  $TC filter add dev $LAN_INTERFACE protocol ip parent 1:0 prio 1 u32 match ip sport $i 0xfc00 flowid 1:10
#  $TC filter add dev $LAN_INTERFACE protocol ip parent 1:0 prio 1 u32 match ip dport $i 0xfc00 flowid 1:10
done
$TC filter add dev $LAN_INTERFACE protocol ip parent 1:0 prio 1 u32 match ip dport $INTERACTIVE_PORT 0xfc00 flowid 1:10

# additional single ports: ssh, VPN, webex, google hangouts
for i in 22 4500 9000 19302 19303 19304 19305 19306 19307 19308 19309; do
  $TC filter add dev $LAN_INTERFACE protocol ip parent 1:0 prio 1 u32 match ip sport $i 0xffff flowid 1:10
  $TC filter add dev $LAN_INTERFACE protocol ip parent 1:0 prio 1 u32 match ip dport $i 0xffff flowid 1:10
done

# also VPN IP range - set this if you know your corporate VPN IP range
#$TC filter add dev $LAN_INTERFACE protocol ip parent 1:0 prio 1 u32 match ip src 1.2.3.4/24 flowid 1:10
#$TC filter add dev $LAN_INTERFACE protocol ip parent 1:0 prio 1 u32 match ip dst 1.2.3.4/24 flowid 1:10

# also icmp
$TC filter add dev $LAN_INTERFACE protocol ip parent 1:0 prio 1 u32 match ip protocol 1 0xff flowid 1:10

## OPTIONAL:
## prioritize any marked packets - use iptables to mark any other prioritized traffic;
## use iptables -t mangle -A PREROUTING -j MARK --set-mark 1 (plus other options)
## NOTE: this is different from ack marking above -- you'd use this with complex iptables rules, e.g. to not
## rate-limit web traffic to/from a specific IP
#$TC filter add dev $LAN_INTERFACE protocol ip parent 1:0 prio 2 handle 1 fw flowid 1:10

# add SFQ / fq_codel / cake / etc (see notes above)
$TC qdisc add dev $LAN_INTERFACE parent 1:10 handle 30: sfq perturb 10
$TC qdisc add dev $LAN_INTERFACE parent 1:11 handle 40: sfq perturb 10
#$TC qdisc add dev $LAN_INTERFACE parent 1:10 handle 30: fq_codel
#$TC qdisc add dev $LAN_INTERFACE parent 1:11 handle 40: fq_codel