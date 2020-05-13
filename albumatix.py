#!/usr/bin/python
# -*- coding: utf-8 -*-

# copyright Stephan Herschel - 2009-2011

# beispielaufruf: python albumatix.py test "[('../christine60/1/*.jpg',5)]"

# Koordinatensystem: 0-Punkt ist links unten!
# koordinatentupels: (<horizontal>,<vertikal>)

# todo:
#20101015: bilder werden in Page.fitPics() aneinander gekoppelt - und zwar passiert die kopplung wenn die
#                     erste kollision passiert, also wenn die erste box aus dem vergroesserungsreigen faellt.
#                     dann werden die nachbarboxes aneinendergekoppelt und 
#                     1. alle nachbarboxes einer kollisionsbox werden auch nicht mehr vergroessert
#                     2. die boxen werden nicht unabhaengig von den nachbarn positioniert.
# 20101001: neuer stack-algo: bisherigen algo so umbauen, dass 2 gegenlaeufige stacks aufgebaut werden: einer von rechts unten (wie bisher)
#                   und einer von links oben. dazu muss die HotPointCollection so umgebaut werden, dass sie von jeder ecke starten kann
# 20101024: initiales festlegen der bildgroesse mit der mindestgroesse (Klasse PIC)
# 20100918: wenn das programm selbständig aus mehreren stackingalgos den besten aussuchen koennte ....
# 20100917: moeglichkeiten, aus gps-tracks  geoinfos zu bekommen, und diese dann als bildlabels anzudrucken, pruefen.
#                      neuer stack-algo: unten von rechts nach links, dann oben von links nach rechts
#                      'aufblasen' unmittelbar nach stack-algo
#                      parameterklasse einfuehren
#                      konzept der textbloecke
# 20100818: man koennte immer in beide richtungen stacken und dann pruefen, welche seite *besser* ist (bessere flaechenausnutzung)
# 20100818: chooseNpositionPics() und chooseNpositionPicsT() vereinigen
# 20100619: Page.fillWindow: windowsize parametrisieren
# 20100619: box: edge etc. cachen - aber achtung bei positionsaenderungen - cache muss geloescht werden
#                      -> positionsaenderungen zentralisieren
# 20100524: locking: passive boxen werdeb durch "adaptOuterBox()" gesperrt, die aktive wird aufgesperrt. 
#                   positionsaenderungen der innerBox sind im gesperrten zustand nicht moeglich
# 20100524: condense-parameter: bilder werden aneinender statt an den aussengrenzen alignt
# 20100511: debug modus: statt die bilder anzudrucken nur 'drahtmodelle' wobei in den boxen
#                 die box/pic-parameter stehen
# 20100425: overlaps treten auf in chooseNpositionPics() und adaptOuterBox()!!
# 20100423: Seitenabstaende gesondert vergeben und individuell steuerbar machen
#                 Unter/ueber dem Bild einen Abstand für Text lassen
# 20100328: OK die in  initOuterBoxes() initialisierte borderL der outerBoxes wird in adaptOuterBoxes() ueberschrieben -> sollte also in 
#            adaptOuterBoxes() geschrieben werden
# 20100327: projekt in module auftrennen ...
#            *  erstes anordnen
#            *  optimieren
# 20100322: corner-handling in Page.fitPics() muss verbessert werden - anscheinend werden die innerBoxes immer ins gleiche eck gestellt
#            ausserdem ueberpruefen, ob das konzept ueberhaupt sinn hat ...
#            des weiteren muss das abschliessende vergroessern in Page.fitPics() noch freigeschaltet werden 
# 20100214: OK adaptouter box verkleinert box nur. aausserdem sollte wir immer ueber alle
#           ueberlappenden outerBoxes loopen (liste?) und fuer diese die outerBox des zu verarbeitenden
#           pics an die innerBox des referenzpics anpassen
# 20100130: zickzackkurs
# 20100124: OK abwechselnde berechnungs- und bewertungszyklen
# 20091211: OK boxalgorithmus: aktuelle innerBox anpassen (i.e. in die outer-box einpassen). mit aktueller
#           outerBox ueberlappende outer-boxes anpassen
# 20090824: OK neues konzept:
#           jedes bild kennt immer seine innere (die begrenzung des bildes selbst) und aeussere box
#           (der bereich, der durch sich aus der lage der nachbarbilder ergibt)
#           aendert nun ein bild seine position oder groesse, dann werden alle benachbarten objekte
#           (i.e das sind objekte deren aeussere box mit der aktuellen ueberlappen) benachrichtigt.
#           diese aktualisieren daraufhin ihre boxdaten.
#           die innere/aeussere box sollten als 4 tupelpaare gespeichert werden.
#           gruppenbildungsalgorithmus: nach jeder iteration (oder nach jeder positionsaenderung einer bildes)
#           wird versucht, gruppen zu bilden oder vorhandne gruppen zu vergroessern. eine gruppe sind
#           mehrere bilder, welche "alignen", d.h. eine gemeinsame fluchtlinie haben (horizontal/vertikal)
#           bilder in einer horizontalen gruppe koennen vertikal nur die hoehe der niedrigsten outer-box
#           annehmen, bei vertikalen gruppen ist die breite durch die schmaelste outer-box beschraenkt.
#           ablauf: entweder werden die bilder im round robin verfahren veranlasst ihre groesse anzupassen,
#           oder es wird mit threads gearbeitet
# 20090823: OK mindestgroesse fuer bilder definieren
# 20090810: OK layoutgruppen: nur gemeinsame groessenaenderung
# 20090806: windowsize parametrisieren! fillWindow()
# 20090803: abbruchsbedingung fuer positionsoptimierung definieren
#           abbruchsbedingung fuer groessenoptimierung definieren
#           groessenoptimierung: graduelles annaehern an idealgroesse?

import errors
errors.catch_errors()

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A6,A5,A4,A3,landscape
from reportlab.lib.units import cm,inch
import glob
from PIL import Image
import getopt
import sys
import logging
import inspect
import random
#import pyexiv2
import copy
import pickle

# fuers debuggen
from reportlab.lib.colors import red,blue,green,yellow, black, grey,white

from abxlogic import Page,Pic
from abxlogic import gParGet,gParSet # globales Parameterdictionary
from mylog import MyLogging

class Album(MyLogging):
	"""
	Albumklasse
	Enthaehlt alle Objekte und Methoden zur Erstellung des Albums
	"""
	def __init__(s,pPicNum=None):
		s.logdbg(inspect.currentframe())

		s.pageL=[]
		s.picL=[]
		#s.pageSize=landscape(A4)
		#s.pageDist={'O':1, 'U':1, 'L':1, 'R':1}
		s.canv=None
		#s.picDirL=pPicDirL
		s.buildPicList(pPicNum)

	def doLayout(s):
		"""
		hier wird das layout des albums erstellt, i.e. die pageL gefuellt
		"""
		s.logdbg(inspect.currentframe())

		if  gParGet('poster')==False:
			# ein album
			counter=0
			while len(s.picL)>0 and (gParGet('optNumOfPages')==None or counter<gParGet('optNumOfPages')):
				#print "loop:-)"
#				picL1=copy.deepcopy(s.picL)
				picL2=copy.deepcopy(s.picL)
				picL3=copy.deepcopy(s.picL)
				page=Page(s.picL,gParGet('pageSize'),'OD1')
#				page1=Page(picL1,gParGet('pageSize'),'OD2')
				page2=Page(picL2,gParGet('pageSize'),'PP1')
				page3=Page(picL3,gParGet('pageSize'),'PP2')
				
#				if page1>page:
#					page=page1
#					s.picL=picL1
				if page2>page:
					page=page2
					s.picL=picL2
				if page3>page:
					page=page3
					s.picL=picL3

#				page=Page(s.picL,gParGet('pageSize'),'PP2')
				#OD2: Positionierung ausserhalb, probleme beim Explode() - aber ist das Problem nur auf diesen Algo beschränkt?
					
#				page_=copy.deepcopy(page) # testing
				page.explode() # hier werden Überlappungen erzeugt!
				page.finalize()
				if not s.boxes:
					page.transform(random.choice(['','H','V','HV']))
					
#				s.pageL.append(page_)
				s.pageL.append(page)
				counter=counter+1
		else:
			# ein poster
			page=Page(s.picL,(int(round(s.canv._pagesize[0])),int(round(s.canv._pagesize[1]))),'PO1')
			page.finalize()
			s.pageL.append(page)

	def createLayoutFile(s):
		"""
		Erzeugen eines Layoutfiles (eine "gepickelte" pageL)
		"""
		s.logdbg(inspect.currentframe())
		
		s.doLayout()
		#26.05.2011: eigentlich muessten auch die parameter mitgespeichert werden
		pickle.dump([gParDict,s.pageL], "picklefile") #hier muss noch der dateinamenauswahl her ...

	def doublePageSize(s,pSize):
		"""
		hier aendern wir die masse fuer doppelseiten
		"""
		return (pSize[0]*2,pSize[1])
	
	def createAlbum(s):
		"""
		Erzeugen eines PDF-Albums
		Parameter:
			pFileName: Namen des Albums
			pDist: Abstand zwischen den Bildern
		"""
		s.logdbg(inspect.currentframe())

		# fuer's debuggen
		s.boxes=False
		leadPage=False

		#if gParGet('doublePage'):
		#	s.canv=canvas.Canvas(gParGet('albumname'),s.doublePageSize(gParGet('pageSize')))
		#else:
		#	s.canv=canvas.Canvas(gParGet('albumname'),gParGet('pageSize'))
		s.canv=canvas.Canvas(gParGet('albumname'),gParGet('pageSize') if not gParGet('doublePage') else s.doublePageSize(gParGet('pageSize')))
		#s.DPI=pDPI
		#wir schreiben die parameter raus
		#s.canv.setStrokeColor(black)
		if leadPage:
			tobj=s.canv.beginText()
			tobj.setTextOrigin(1*cm, 10*cm)
			tobj.setFont("Courier", 10)
			for i in gParGet().iteritems():
				tobj.textLine(str(i))
			s.canv.drawText(tobj)
			s.canv.showPage()
		#s.canv.drawString(10*cm, 1*cm, str(s.gParDict))
		#print s.gParDict['optNumOfPages'],len(s.picL)

		if True:
			s.doLayout()
		else:
			# hier kommt die funktionalitaet fuer's laden eines vorhandenen layouts hin ...
			#26.05.2011: eigentlich muessten auch die parameter mitgespeichert werden
			gParDict,s.pageL=pickle.load("picklefile")
		
		pagesOnCanv=1
		if gParGet('doublePage'):
			pagesOnCanv=2
		
		pageCounter=0
		docCounter=0
		for i in range(0,len(s.pageL),pagesOnCanv): 
			s.beamToCanvas(s.pageL[i:i+pagesOnCanv],i+1)
			# ... beamToCanvas erhaelt soviele seiten wie auf den canvas sollen
			pageCounter=pageCounter+1
			if gParGet('maxPDFlength')!=None and pageCounter>=gParGet('maxPDFlength'):
				# logik fuer alben die aus mehreren PDFs bestehen
				pageCounter=0
				s.canv.save()
				docCounter=docCounter+1
				s.canv=canvas.Canvas(gParGet('albumname')+str(docCounter),gParGet('pageSize'))
				s.canv=canvas.Canvas('.'.join([gParGet('albumname').split('.')[0]+str(docCounter),gParGet('albumname').split('.')[1]]),gParGet('pageSize') if not gParGet('doublePage') else s.doublePageSize(gParGet('pageSize')))
		s.canv.save()
		

	def buildPicList(s,pPicNum=None):
		"""
		Aufbau der Bilderliste
		(Einlesen aus den entsprechenden Verzeichnissen)
		"""
		s.logdbg(inspect.currentframe())

		#print 'gParGet(''albumgloblist''): ',gParGet('albumgloblist')
		for d in gParGet('albumgloblist'):
			for f in glob.glob(d[0]):
				if gParGet('poster')==True:
					# im fall eines posters setzen wir die min-diagonale 1 (wird später aus der anzahl der bilder und der postergroesse berechnet)
					minDiag=1
				else:
					minDiag=d[1]*cm
				s.picL.append(Pic(f,minDiag))
				
		# beschraenkung der bilderanzahl (sinnvoll im zusammenhang mit postern)
		if pPicNum!=None:
			s.picL=s.picL[:pPicNum]

		#logging.info('picList: '+str(s.picL))
		
		if len(s.picL)==0:
			print ("Error: Empty list of pictures!")
			exit(1)

		# sortiere bilderliste ...
		if gParGet('optUseExif'):
			try:
				s.picL.sort(key=lambda x: x.getDateTime(),reverse=False)
			except TypeError:
				# wenn's probleme gibt, den zeitstempel der bilder zu bekommen
				s.picL.sort(key=lambda x: x.getName(),reverse=False)
		else:
			s.picL.sort(key=lambda x: x.getName(),reverse=False)

		s.loginfo('picList sorted: '+str(s.picL))
		

	def shift(s,pX,pPageOnCanvas):
		"""
		mehrere pages auf canvas: projezieren der x-koordinate von der page auf den canvas
		"""
		if pPageOnCanvas==0:
			return pX
		else:
			return pX+(gParGet('pageSize')[0]*pPageOnCanvas)
		
	
	def beamToCanvas(s, pPageL,pPageNum):
		"""
		Befuellen eines Report-Lab Canvas
		"""
		s.logdbg(inspect.currentframe())
		s.loginfo('picsOnPage: '+str(pPageL[0].getPicList()))

		#print 'beamToCanvas - s.picsOnPage:',pPage.getPicList()
		
		hotPoints=False
		
		for j,pPage in enumerate(pPageL):
			s.canv.setFillColorRGB(*gParGet('backgroundColour'))
			s.canv.rect(s.shift(0,j), 0, gParGet('pageSize')[0], gParGet('pageSize')[1], fill=1,stroke=0)
		
			i=0
			for p in pPage.getPicList():
				if not s.boxes:
					s.canv.drawInlineImage(p.getImage(gParGet('optDpi')),s.shift(p.x(),j),p.y(),p.w(),p.h(pNetto=True))
					if p.getCaption()!=None and gParGet('text'):
						s.canv.setFillColor(black)
						s.canv.setFont("Helvetica", 9)
						s.canv.drawCentredString(s.shift(p.x(),j)+p.w()//2,p.y()-gParGet('picFooterHeight'),p.getCaption())
				else:
					s.canv.setStrokeColorRGB(0.8, 0.8, 0.8)
					s.canv.setFillColorRGB(0.8, 0.8, 0.8)
					s.canv.rect(s.shift(p.x(),j),p.y(),p.w(),p.h(), fill=1)

					s.canv.setFillColor(black)
					tobj=s.canv.beginText()
					tobj.setTextOrigin(s.shift(p.x(),j)+5,p.y()+p.h()-15)
					tobj.setFont("Courier", 10)
					tobj.textLine(p.filename.split('/')[-1])
					tobj.textLine(str(p.minDiagonale))
					tobj.textLine(str(p.outerBox.borderL)) #+' '+str(p.innerBox.borderL))
					tobj.textLine(str({'x':p.innerBox.x,'y':p.innerBox.y,'h':p.innerBox.h,'w':p.innerBox.w}))
					tobj.textLine(str({'x':p.outerBox.x,'y':p.outerBox.y,'h':p.outerBox.h,'w':p.outerBox.w}))
					tobj.textLine(p.getText())
					s.canv.drawText(tobj)

				if s.boxes:
					if i%4==0:
						s.canv.setStrokeColor(blue)
					elif i%4==1:
						s.canv.setStrokeColor(green)
					elif i%4==2:
						s.canv.setStrokeColor(yellow)
					else:
						s.canv.setStrokeColor(red)
					i=i+1
					s.canv.rect(p.outerBox.x,p.outerBox.y,p.outerBox.w,p.outerBox.h)
			# zu debuggingzwecken koennen wir die hotpoints anzeigen
			if hotPoints and pPage.getHotPoints()!=None:
				hpL=pPage.getHotPoints().getList()
				for hp in hpL:
					if hp[2]=='RO':
					  s.canv.setFillColor(red)
					else:
					  s.canv.setFillColor(green)
					s.canv.circle(s.shift(hp[0],j), hp[1], 3, fill=1)

			if gParGet('text'):
				if gParGet('poster'):
					# Anzeigen des Copyright-hinweises
					if sum(gParGet('backgroundColour'))/3.0  >0.5:
						s.canv.setFillColor(black)
					else:
						s.canv.setFillColor(white)
					s.canv.setFont("Helvetica", 8)
					s.canv.drawCentredString(s.shift(int(pPage.pagesize[0]/2),j),int(gParGet('pageDist')['U']/2),'a l b u m a t i x . c o m')
				else:
					# Anzeigen des Datums
					s.canv.setFillColor(black)
					s.canv.setFont("Helvetica", 11)
					s.canv.drawCentredString(s.shift(int(pPage.pagesize[0]/2),j),pPage.pagesize[1]-1*cm,pPage.getPicList()[0].getDateTime().date().strftime('%d.%m.%Y'))
					
					# Anzeigen der Seitennummer 
					s.canv.setFillColor(black)
					s.canv.setFont("Helvetica", 11)
					s.canv.drawCentredString(s.shift(int(pPage.pagesize[0]/2),j),1*cm,'- '+str(pPageNum)+' -')
			
		s.canv.showPage()
		# loeschen der bilderliste um speicherplatz freizugeben ... (nuetzt das was???)
		#s.picsOnPage=[]



class Main(MyLogging):
	def __init__(s):
		# parameterdictionary - set defaults:
		gParSet('optDpi',50)
		gParSet('optBorder',10)
		gParSet('optUseExif',False)
		gParSet('optNumOfPages',None )
		gParSet('winSize',30)
		gParSet('maxPDFlength',None)
		gParSet('pageSize',landscape(A4))
		gParSet('pageDist',{'O':int(round(1.5*cm)), 'U':int(round(1.5*cm)), 'L':int(round(1.5*cm)), 'R':int(round(1.5*cm))})
		#gParSet('backgroundColour',(0.85, 0.85, 0.85))
		#gParSet('backgroundColour',(0, 0, 0))
		#gParSet('backgroundColour',(0.75, 0.75, 0.75))
		gParSet('backgroundColour',(0.9, 0.9, 0.9))
		gParSet('fixSizeThreshold',1*cm)
		gParSet('picFooterHeight',10)
		gParSet('text',False)
		gParSet('poster', False)
		gParSet('bucketsize', 2.5*3600) # in sekunden
		gParSet('doublePage',False)
		gParSet('optNumOfPics',None)
		gParSet('crop',0)
	
	def main(s):
		s.logstart()

		try:
			opts,args=getopt.getopt(sys.argv[1:],'',['dpi=','border=','exif','numOfPages=', 'windowSize='
						, 'pageSize=','pageDist=','backgroundColour=','maxPDFlength=', 'poster','double', 'text','numOfPics='
						, 'crop='])
			for o in opts:
				if o[0]=='--dpi':
					gParSet('optDpi',int(o[1]))
				if o[0]=='--border':
					gParSet('optBorder',round(float(o[1])*cm))
				if o[0]=='--exif':
					gParSet('optUseExif',True)
				if o[0]=='--numOfPages':
					gParSet('optNumOfPages',int(o[1]))
				if o[0]=='--pageSize':
					gParSet('pageSize',tuple([x*cm for x in eval(o[1])]))
				if o[0]=='--windowSize':
					gParSet('winSize',int(o[1]))
				if o[0]=='--pageDist':
					#wir interpretieren den parameter als dictionary
					pageDistD=eval(o[1])
					# jetzt bringen wir das dictionary auf die richtige einheit
					for x in list(pageDistD):
						pageDistD[x]=pageDistD[x]*cm
					gParSet('pageDist',pageDistD)
				if o[0]=='--maxPDFlength':
					gParSet('maxPDFlength',int(o[1]))
				if o[0]=='--backgroundColour':
					gParSet('backgroundColour',[x/255.0 for x in list(eval(o[1]))])
				if o[0]=='--poster':
					gParSet('poster', True)
				if o[0]=='--double':
					gParSet('doublePage', True)
				if o[0]=='--text':
					gParSet('text', True)
				if o[0]=='--numOfPics':
					gParSet('optNumOfPics',int(o[1]))
				if o[0]=='--crop':
					gParSet('crop',int(o[1]))
			if len(args)< 2:
				raise getopt.GetoptError('wrong number of arguments','')
		except getopt.GetoptError as e:
			print (e)
			print ("parameters: [--dpi] [--border] [--exif] [--numOfPages] [--pageSize] [--windowSize] album-name image-group-list")
			print ("image-group-list: [(<globstring>,<minsize>), ..]")
			print ("--dpi: resolution in dpi")
			print ("--border: border between pics")
			print ("--exif: order by exif timestamp")
			print ("--numOfPages: constrain number of pages")
			print ("--pageSize: size of page in cm: (<x>,<y>)")
			print ("--windowSize: number of pics to take into account for each page")
			print ("--pageDist: margins in cm: {'O':<upper>, 'U':<lower>, 'L':<left>, 'R':<right>}")
			print ("--maxPDFlength: maximum length of a single PDF document")
			print ("--backgroundColour: give a RGB-Tuple (like '(0,0,0)'")
			print ("--double: create double pages")
			print ("--poster: create a poster on one page (not all of the other parameters apply!)")
			print ("--text: display text")
			print ("--numOfPics: constrain number of pics (in combination with option '--poster')" )
			print ("--crop: crop each pics by the given number of pixels" )
			print ("for example: python albumatix.py --dpi=200 test \"[('../christine60/1/*.jpg',5)]\"")
			sys.exit(2)

		gParSet('albumname',args[0]+'.pdf')
		gParSet('albumgloblist',eval(args[1]))

		a=Album(gParGet('optNumOfPics'))
		a.createAlbum()



if __name__ == '__main__':
	# wird nur ausgefuehrt, wenn albumatix.py direkt ausgefuehrt wird ...
	run=Main()
	run.main()


#import hotshot
#prof=hotshot.Profile("hotshot_albumatix_stats")
#prof.runcall(run.main)
#prof.close()
