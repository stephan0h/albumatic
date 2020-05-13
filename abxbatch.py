# copyright Stephan Herschel - 2009-2011

# batch fuer posterization
import os
import urllib
from reportlab.lib.units import cm
import subprocess
import time
import sys, traceback
#import random

import facebook
import albumatix
import MySQLdb

import hashlib

# fuer's email
import smtplib
from email.mime.text import MIMEText

gDbConnection=('localhost','stephan0h_abx','apfel','stephan0h_abx')
gBaseFolder='/home/stephan0h/tmp/'
gTargetFolder='/home/stephan0h/tmp/'
gPublishFolder='/home/stephan0h/webapps/albumatix/'

gSMTP=("smtp.webfaction.com",25)
gMailLogin=('abx','f2530e1c')
gLetterEN='abxLetterEN.txt'
gLetterDE='abxLetterDE.txt'

gHelloMessage='Made with http://www.albumatix.com'

# ablauf
# 1. pruefung ob neue auftraege vorhanden sind
# 1.1 nein: selbstaufruf mit at-command  - intervall 15 minuten oder so
# 1.2 loop ueber die auftraege
# 1.2.1 erzeugen eines auftragsverzeichnisses
# 1.2.2 herunterladen der pics
# 1.2.3 setzen der parameter und aufruf von albumatix
# (1.2.4) konvertieren des pdfs in jpg (convert!)
# (1.2.5) loeschen der ausgangsbilddaten
# 1.2.6 setzen des auftrages auf finished
# 1.5 selbstaufruf mit at-command ...

def calcBorder(pPicSum):
	aPar=-0.00333
	bPar=0.43333
	ret=round(aPar*pPicSum+bPar,2)
	return ret if ret>=0.1 else 0.1 # minimum 1mm

while 1:
	conn=MySQLdb.connect(*gDbConnection)
	# 1. pruefung ob neue auftraege vorhanden sind
	cursor1=conn.cursor()
	cursor1.execute("select id,order_date,source,auth,alb_id,bg_rgb,order_lang from orders_order where orderstatus='_' order by id")
	oRec=cursor1.fetchone()
	while oRec != None:
		try:
			# 1.2 loop ueber die auftraege
			# 1.2.1 erzeugen eines auftragsverzeichnisses
			orderName='abx'+str(oRec[0])
			#hashval=hashlib.md5(orderName).hexdigest()
			os.mkdir(gBaseFolder+orderName)
			# 1.2.2 herunterladen der pics
			graphObj = facebook.GraphAPI(oRec[3])
			profil=graphObj.get_object('me')
			if oRec[4]=='$$FRIENDS$$':
				#Freundealbum
				frie=graphObj.get_connections('me','friends')[u'data']
				picSum=len(frie)
#				friendtags=[]
				for f in frie[0:800]:
#					friendtags.append({"tag_uid":str(f[u'id'])})
					outF=open(gBaseFolder+orderName+'/'+f[u'id']+'.jpg','w')
					inF=urllib.urlopen('https://graph.facebook.com/'+f[u'id']+'/picture?access_token='+oRec[3]+'&type=large')
					outF.write(inF.read())
					inF.close()
					outF.close()
					
			else:
				pics=graphObj.get_connections(oRec[4], "photos")[u'data']
				picSum=len(pics)
				for p in pics[0:800]:
					outF=open(gBaseFolder+orderName+'/'+p['source'].split('/')[-1],'w')
					inF=urllib.urlopen(p['source'])
					outF.write(inF.read())
					inF.close()
					outF.close()
			
			# pruefen, ob bilder heruntergeladen wurden
			dirlist=os.listdir(gBaseFolder+orderName)
			if dirlist==[]:
				cursor3=conn.cursor()
				cursor3.execute("update orders_order set orderstatus='?' where id="+str(oRec[0]))
				cursor3.close()
			else:
				
				# 1.2.3 setzen der parameter und aufruf von albumatix
				mObj=albumatix.Main() # setzen der defaultparameter

				# rgb
				rgb=[]
				for x in range(3):
					rgb.append(int(oRec[5][x*2:x*2+2],16)/255.0)

				albumatix.gParSet('poster',True)
				albumatix.gParSet('pageSize',(25*cm,25*cm))
				albumatix.gParSet('backgroundColour',tuple(rgb))
				albumatix.gParSet('optDpi',300)
				albumatix.gParSet('optBorder',calcBorder(picSum)*cm)
				albumatix.gParSet('optUseExif',False)
				albumatix.gParSet('pageDist',{'O':int(round(1.2*cm)), 'U':int(round(1.2*cm)), 'L':int(round(1.2*cm)), 'R':int(round(1.2*cm))})
				albumatix.gParSet('text',True)

				albumatix.gParSet('albumname',gTargetFolder+orderName+'.pdf')
				albumatix.gParSet('albumgloblist',[(gBaseFolder+orderName+'/*.[jJ][pP][gG]',)])

				alb=albumatix.Album()
				alb.createAlbum()

				# (1.2.4) konvertieren des pdfs in jpg (convert!)
				subprocess.call(['pdf2ps',gTargetFolder+orderName+'.pdf',gTargetFolder+orderName+'.ps'])
				subprocess.call(['convert','-density','300','-resize','1600x1600',gTargetFolder+orderName+'.ps',gPublishFolder+orderName+'.jpg'])
				subprocess.call(['rm',gTargetFolder+orderName+'.ps'])
				# thumbnail ...
				#subprocess.call(['convert',gTargetFolder+orderName+'.jpg', '-resize', '250x250', gPublishFolder+orderName+'_thmb.jpg'])
				# zugriffsrechte auf pdf-file werden entzogen
				#subprocess.call(['chmod','000',gPublishFolder+orderName+'.pdf'])
				# 1.2.4a: upload des jpegs
				fP=open(gPublishFolder+orderName+'.jpg','rb')
				try:
#					try:
#						random.shuffle(friendtags)
#						graphObj.put_object('me','photos',source=fP,message=gHelloMessage,tags=str(friendtags[0:50]).replace("'",'"'))
#					except NameError:
					graphObj.put_object('me','photos',source=fP,message=gHelloMessage)
				except HTTPError:
					# wir vermerken den fehler und machen weiter mit dem email ...
					print "Error@"+str(oRec[0])+": HTTPError!"
					pass
				fP.close()
				#  1.2.4a: versenden des mails
				fL = open(gLetterDE if oRec[6]=='DE' else gLetterEN, 'r')
				#msg=MIMEText(fL.read().replace('$$link$$','http://www.albumatix.com/prv/'+hashval))
				msg=MIMEText(fL.read().replace('$$link$$','http://download.albumatix.com/'+orderName+'.jpg'))
				fL.close()
				msg['Subject']='Your poster is ready!'
				msg['From']='info@albumatix.com'
				msg['To']=profil[u'email']
				# mail an mich selber
				msg['Bcc']='info@albumatix.com'
				smtpserver = smtplib.SMTP(*gSMTP)
				smtpserver.ehlo()
				smtpserver.starttls()
				smtpserver.login(*gMailLogin)
				smtpserver.sendmail(msg['From'],[msg['To'],msg['Bcc']],msg.as_string())
				smtpserver.close()

				# (1.2.5) loeschen der ausgangsbilddaten
				#subprocess.call(['rm' ,'-rf',gBaseFolder+orderName+'.*'])
				# nur der bilderordner wird geloescht
				subprocess.call(['rm' ,'-rf',gBaseFolder+orderName])
				# 1.2.6 setzen des auftrages auf finished und setzen des hashwertes
				cursor2=conn.cursor()
				cursor2.execute("update orders_order set orderstatus='F', email='"+profil[u'email']+"' where id="+str(oRec[0]))
				cursor2.close()
		except:
			print "Error@"+str(oRec[0])+":"
			traceback.print_exc(file=sys.stdout)
			
			cursor3=conn.cursor()
			cursor3.execute("update orders_order set orderstatus='?' where id="+str(oRec[0]))
			cursor3.close()
		# naechster eintrag
		oRec=cursor1.fetchone()
#			break

	cursor1.close()
	conn.close()
	# 1.5 selbstaufruf mit at-command ... oder eben time.sleep()
#	break
	time.sleep(60*5) # 15 minuten nix tun ...

