GHb A   - $15/monthaddes & Backend (Docker handles routing)    proxy_cache_bypass $http_upgrade;
     Auto-Deploythe sePaste c``nthropic AGroq  branchDeploys a✅ SSH into server
ssh -i your-key.pem ubuntu@YOUR_EC2_P

# I pointing to your IPTest aYour site is now live at `https://yourdomain.com` 🎉

aily### View Logs
SSH into server
ssh -i your-key.pem ubuntu@YOUR_EC2_IP

# al l

#View specific service
docker-compose logs -f ```
##S```bash
```
##ManualDly```sh
c~/fedfocu origin main```
##Sp/Strt
```bah
#Sop ll svicesdown

#Strt all servis
ocker-comseu -dWhnond
-A-bsffZwntie eoyMgfrucureMult-giply###fsAtcyscaes110ansbsdllpoymnt (nowim-Hethchksdauoy-aylfwyuC:- ES Fargae~$30-50/mn**AplicaLoadBc$16/mth
**Ta:**~$50-70/mhERRsybshwc reposyrepi-n2hDkIg#GtECRlginwcr-gi-sword--resast-1|\dorlog-rAWS--passd-tdin\YOUR_AWS_ACCOUNT.dr..e-1.zowc#apuck-tisht-fed.ckerg :lat\YOUR_AWSACCOUNT.dk.e-1azoaws.mnig-feedtedcku\YOURAWSACCOUNT.k.r.--1.mzaw.om:la3GitHuAishdlesthere!
`.ghub/wokfs/-w-ec.l` edcfured- Add AWS cisoGtHbscs:
`WSCCESS_ID`  `WSECREACSSKY`4**CraeECSsurcs (AWSCno):
  Crea ECSuer-CaeTkDf(seDkgeomECR)
vcwhSclg****Finsight F****Coninrwn'startdocker-composeogscknd
docke-compoe exec backend docker-compose restart
an'tconnct to app
- Check secuity gup allow port 80-Check Dckeis uing:`cker-copose ps`
- Check Ngx:`sudsystemctl status nginx`
- hecklgs: `docke-compose lo`

###Databaseissues
``sh
dor-compose exec backe python dbit_db
docker-compose restart backend

### Ou f disk space```bsh
# Cn up Docke
dockrsystemprune-a
```

---

##onitorng

### ClouWatch (AWS Consoe)
- EC2 mtics (CPU, mmory network)-Setuparms f h CPUmemy
 View logs om cers
###ManualChecksbashCheckDoker sttus
docker-compoeps
# k dis space
df -h

#Ceckmemory
e-h

#Checksyste resour
top
```

---

##Backp Stategy

###Dataase Bupbash
# Creae backu cat > ~backup.sh <<'EOF'
#!/bi/bash
DATE=$(da +%Y%m%d_%H%M%S)
c ~feedfocu
docke-s exec -T backed qlite3 app/is.b dump > backup_$DATE.qlaws3cpbacku_$DATE.ql s3up-buckt/
EOF

chmo +x ~/backupsh

# Run d vi cron
crontab -e
# Add: 0 2 * * * ~/backu.shVectrDatabaBackup
```bah# Backup 
tar-czf choma_back.rgzchrom_db/
wss3pchrma_backup.a.gz s3:/u-up-buckt/```
Cs Breakdwn

| Sevce | Mothly Cost ||---------|-------------|| EC2 t3.sml** | $15 |
| **20GB EBS Storg** | $2 |
| **Data Trasf(50GB) | $4 ||**Roe 53 (ponal)**| $0.50 |
| **Tota** | **$21-22/mnth** |
###ECSFrgte (Pouction):|Svice | Monhly Cot ||---------|-------------|| agat (13 asks) | $30-50 ||**Applatio LoaBaancer** | $16 ||**DataTrar**|$5-10||**To**|**$50-75mth** |eiyCheckt
[]SSH kbsedauthetcaion only[ ] irewllfigd(fw)-[] SSL cerificateintld[]Reuruats: `udoapupate &&supt uprade` []Scs nvirmntvrbles, no cod [ ]Daabaseups configur
- [ ]CloudWachalars set up
- [ ] Securty gup rett SSH to your IP NextStps

**Wk 1** Getcomfortbe ith EC2
- [x] app with Dockr- [ ] Add domn nme (Route 53)
- []Seup SSLcrtificte
- [ ] Confgur CloudWachmniorg

**Week 2-3:**Ler Docker & AWS
- []UndsadDckercontairs [ ]Practicemanal 
- [ ] Set upautatedbackups []Moto lgs ad trics

**Moh 2:**Upgd to ECS []uhimstER []CatECSluste
- [ ] Supa-sclg []Impemen zerodwme ds

---##UefuResources

 [AWS EC2Documentton](https://docs.as.amzon.come2/)- [Docke Documentt](https://dos.ocker.com/)
- [ECSBet Practics](http:/docs.as.zn.om/AazoECS/laetbetpcticesguide/)- [Cetbot SSLGide](htts://certbot.eff.org/)
---**'eredy to deloy!** 🚀Follo the Quck Start steps above and you'~20.