{% if grains['os'] == 'CentOS' %}

# START CentOS pkgrepo tests
{% if grains['osrelease'].startswith('6.') %}
epel-salttest:
  pkgrepo.managed:
    - humanname: Extra Packages for Enterprise Linux 6 - $basearch (salttest)
    - comments:
      - '#baseurl=http://download.fedoraproject.org/pub/epel/6/$basearch'
    - mirrorlist: https://mirrors.fedoraproject.org/metalink?repo=epel-6&arch=$basearch
    - failovermethod: priority
    - enabled: 1
    - gpgcheck: 1
    - gpgkey: file:///etc/pki/rpm-gpg/RPM-GPG-KEY-EPEL-6-salttest
    - require:
      - file: /etc/pki/rpm-gpg/RPM-GPG-KEY-EPEL-6-salttest

/etc/pki/rpm-gpg/RPM-GPG-KEY-EPEL-6-salttest:
  file.managed:
    - source: salt://pkgrepo/files/RPM-GPG-KEY-EPEL-6-salttest
    - user: root
    - group: root
    - mode: 644
{% elif grains['osrelease'].startswith('5.') %}
epel-salttest:
  pkgrepo.managed:
    - humanname: Extra Packages for Enterprise Linux 5 - $basearch (salttest)
    - comments:
      - '#baseurl=http://download.fedoraproject.org/pub/epel/5/$basearch'
    - mirrorlist: http://mirrors.fedoraproject.org/mirrorlist?repo=epel-5&arch=$basearch
    - failovermethod: priority
    - enabled: 1
    - gpgcheck: 1
    - gpgkey: file:///etc/pki/rpm-gpg/RPM-GPG-KEY-EPEL-5-salttest
    - require:
      - file: /etc/pki/rpm-gpg/RPM-GPG-KEY-EPEL-5-salttest

/etc/pki/rpm-gpg/RPM-GPG-KEY-EPEL-5-salttest:
  file.managed:
    - source: salt://pkgrepo/files/RPM-GPG-KEY-EPEL-5-salttest
    - user: root
    - group: root
    - mode: 644
{% endif %}
# END CentOS pkgrepo tests

{% elif grains['os'] == 'Ubuntu' %}

# START Ubuntu pkgrepo tests
{% set codename = grains['oscodename'] %}
gpodder-ppa:
  pkgrepo.managed:
    - humanname: gPodder PPA
    - name: deb http://ppa.launchpad.net/thp/gpodder/ubuntu {{ codename }} main
    - dist: {{ codename }}
    - file: /etc/apt/sources.list.d/gpodder.list
    - keyid: 89617F48
    - keyserver: keyserver.ubuntu.com

nginx-ppa:
  pkgrepo.managed:
    - ppa: nginx/development

pkgrepo-deps:
  pkg.installed:
    - pkgs:
      - python-apt
      - python-softare-properties
    - require_in:
      - pkgrepo: gpodder-ppa
      - pkgrepo: nginx-ppa
# END Ubuntu pkgrepo tests

{% else %}

# No matching OS grain for pkgrepo management, just run something that will
# return a True result
date:
  cmd:
    - run

{% endif %}
