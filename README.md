
- deploy_vpn_server.sh - развертываение сервера в один клик (должно быть доменное имя для ssl-сертификата)
- network_monitor.py - монитор загруженности сетевого интрфейса, отпраляет все данные в кафку
- network_monitor.service - сервис, запускающий монитор через start.sh

Настойки учетных записей пользователей:
/etc/ipsec.secrets

Перезапуск ipsec:
ipsec restart

Насторойки конфигурационного файла /etc/ipsec.conf:
```
config setup
  strictcrlpolicy=yes
  uniqueids=never

conn roadwarrior
  auto=add
  compress=no
  type=tunnel
  keyexchange=ikev2
  fragmentation=yes
  forceencaps=yes

  # https://docs.strongswan.org/docs/5.9/config/IKEv2CipherSuites.html#_commercial_national_security_algorithm_suite
  # ... but we also allow aes256gcm16-prfsha256-ecp256, because that's sometimes just what macOS proposes
  #ike=aes256gcm16-prfsha384-ecp384,aes256gcm16-prfsha256-ecp256!
  #esp=aes256gcm16-ecp384!
  ike=aes256gcm16-prfsha384-ecp384,aes256gcm16-prfsha256-ecp256,aes128gcm16-prfsha256-ecp256,aes256-sha256-modp2048!
  esp=aes256-sha256-modp2048-modpnone,aes256gcm16-ecp384,aes128gcm16-ecp256,aes256-sha256!
  dpdaction=restart
  dpddelay=900s
  rekey=no
  left=%any
  leftid=@${VPNHOST}
  leftcert=cert.pem
  leftsendcert=always
  leftsubnet=0.0.0.0/0
  right=%any
  rightid=%any
  rightauth=eap-mschapv2
  eap_identity=%any
  rightdns=${VPNDNS}
  rightsourceip=${VPNIPPOOL}
  rightsendcert=never
```
