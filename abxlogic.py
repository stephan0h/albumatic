# -*- coding: utf-8 -*-

# copyright Stephan Herschel - 2009-2011


import logging
import inspect
from PIL import Image
import copy
import random
from reportlab.lib.units import cm,inch
import mmap
from operator import itemgetter
#import os
import datetime

try:
	import pyexiv2
except ImportError:
	pass


from mylog import MyLogging

gParDict={} # parameter dictionary

def gParGet(pPar=None):
	global gParDict
	if pPar==None:
		return gParDict
	else:
		return gParDict[pPar]

def gParSet(pPar,pVal):
	global gParDict
	gParDict[pPar]=pVal

class MyMap(mmap.mmap):
	"""
	patch der mmap-klasse
	grund: wir brauchen eine parameterlose read()-methode
	"""
	def setSize(s):
		"""
		hier kann die groesse des files im vorhinein vermerkt werden
		"""
		s.size=s.tell()
	def read(s,length=None):
		"""
		der patch der mmap.read()-methode
		"""
		if length==None:
			return mmap.mmap.read(s,s.size)
		else:
			return mmap.mmap.read(s,length)

class AppError(Exception):
	"""
	spezifische fehler
	"""
	def __init__(s, expression, message):
		s.expression = expression
		s.message = message

	def __str__(s):
		return s.message+' '+repr(s.expression)

class CmpError(Exception):
	"""
	vergleichsfehler
	"""
	def __init__(self):
			pass

class Page(MyLogging):
	"""
	Seitenklasse
	Enthaelt alle Objekte und Methoden zum Aufbau einer Seite
	"""
	def __init__(s,pPicL,pPageSize,pAlgo):
		"""
		Parameter:
		pPicL 			... die Bilderliste
		pPageSize 	... Seitengroesse
		pAlgo 			... gibt an, welcher Algorithmus verwendet werden soll
		"""
		s.logdbg(inspect.currentframe())

		s.algoD={'OD1':s.chooseNpositionPicsOpposedDirection ,'OD2':s.chooseNpositionPicsOpposedDirectionT \
		               ,'PP1':s.chooseNpositionPics,'PP2':s.chooseNpositionPicsT, 'PO1':s.positionPoster}
		s.algo=pAlgo

		#s.picsOnPage=[]
		# weitere attribute die den seitenaubfau bestimmen
		s.picL=pPicL
		s.dist=gParGet('optBorder')
		s.distRough=round(s.dist*5) #bilddistanz fuer grobpositionierung
		s.pageDist=gParGet('pageDist')
		s.winSize=gParGet('winSize')
		#s.pagesize=(int(s.canv._pagesize[0]),int(s.canv._pagesize[1]))
		s.pagesize=pPageSize
		s.loginfo('Pagesize: '+str(s.pagesize))
#		s.pageBox=Box()
#		s.pageBox.setBoxFromLevels({'L':s.pageDist['L']-s.dist,\
#		                                             'R':s.pagesize[0]-s.pageDist['R']+s.dist,\
#		                                             'U':s.pageDist['U']-s.dist,\
#		                                             'O':s.pagesize[1]-s.pageDist['O']+s.dist})
		#beruecksichtigung der seitenraender
		s.pageBox=Box({'L':s.pageDist['L']-s.dist,\
		                            'R':s.pagesize[0]-s.pageDist['R']+s.dist,\
		                            'U':s.pageDist['U']-s.dist,\
		                            'O':s.pagesize[1]-s.pageDist['O']+s.dist})
		s.picsOnPage=[]

		s.neighbours={}
		# ... beinhaltet die information ueber die nachbarn der bilder auf dieser seite in folgendem format:
		# {<bild-hash>:{'O':<bild>,'U':<bild>,'R':<bild>,'L':<bild>}, ...}

		# wenn das gesetzt ist beschraenken wir uns bei der nachbarsuche nur auf den durch den radius bestimmten bereich
		#s.radiusNeighbourSearch=None

		if s.algo!='PO1':
			# fuer's posterisieren brauchen wir das nicht
			s.fillWindow()
		#s.fitPics()

		s.algoD[s.algo]()
		
		s.hotPoints=None

	def getPicList(s):
		"""
		return picList
		"""
		return s.picsOnPage

	def finalize(s):
		"""
		nachdem die bilder grob angeordnet und bewertet wurden erfolgt hier die finalisierung
		"""
		def findCandsAndAdaptOuterBox(currPic):
			"""
			kombination aus der suche aller boxen, die mit der aktuellen ueberlappen und aufruf
			von adaptOuterBox() mit der gefundenen kandidatenliste
			"""
			if s.picsOnPage[currPic].getOuterBoxOverlaps()==[]:
				candL=[]
				# ist s.radiusNeighbourSearch gesetzt (nur bei Poster) dann werden Nachbarn nur innerhalb eines Bereiches gesucht.
				# dieser code funktioniert noch nicht ...
#				picsInRadius=None
#				if s.radiusNeighbourSearch!=None:
#					picsInRadius=[x for x in s.picsOnPage if s.picsOnPage[currPic].innerBox.center().distance(x.innerBox.center())<s.radiusNeighbourSearch]
#				for j,q in enumerate(s.picsOnPage if picsInRadius==None else picsInRadius):
				for j,q in enumerate(s.picsOnPage):
					if currPic!=j:
						if s.picsOnPage[currPic].outerBox.intersecting(s.picsOnPage[j].outerBox)!=None:
							# die outerBoxes ueberlappen sich
							candL.append(s.picsOnPage[j])
				s.picsOnPage[currPic].setOuterBoxOverlaps(candL)
			else:
				candL=s.picsOnPage[currPic].getOuterBoxOverlaps()
			s.adaptOuterBox(s.picsOnPage[currPic],candL)
		# funktionsende ##################

		# bilder auf der seite verteilen
		#s.explode()
		#s.findOverlaps()
		#return
		# outerBoxes initialisieren
		s.initOuterBoxes()
		s.findPositionError()
		#return

		# vorgehen: abwechselnd wird je ein berechnungs- und bewertungszyklus
		#           durchgefuehrt. vor dem berechnungszyklus merken wir uns das page-objekt
		#						um im fall, dass wir in bewertungszyklus ueberlappungen feststellen,
		#						zuruecksteigen zu koennen
		#						kommt es zu uebelappungen verkleinern wir im naechsten berechnungsschritt
		#						die schrittweite ...
		schrdirection='H'
#		cornerL=['OL','UR','UL','OR']
#		cornCnt=0

		# indexliste
		collisionIndex=None
		firstReduction=True
#		allowSmallChanges=True
#		smallChangesSmallerThen=16
		cnt=0
		schrweite=32
		while schrweite>2:
			picIndL=list(range(0, len(s.picsOnPage)))
			print ('schrweite: ',schrweite)
			while len(picIndL)>=1:
				cnt+=1
				print ('fitPics-while: picIndL', picIndL, collisionIndex)
				
				if collisionIndex!=None:
#					if s.neighbours!={}:
#						# zuerst werden die bilder entfernt, die den schlawiner als nachbar haben ...
#						il=[x for x in picIndL if s.picsOnPage[x] in s.neighbours[hash(s.picsOnPage[collisionIndex])].values()]
#						print 'il: ',il
#						for i in il:
#							picIndL.remove(i)
					# und dann der schlawiner selbst
					picIndL.remove(collisionIndex)
					if len(picIndL)<=1:
						break
					collisionIndex=None

				# sicherungskopie
				#picsOnPage_bak=copy.deepcopy(s.picsOnPage)
				picsOnPage_bak=copy.copy(s.picsOnPage)	# eine shallow-copy funktioniert auch ...
				# berechnungszyklus
				random.shuffle(picIndL)
				for i in picIndL:
					#print 'fitPics-for: pics vergroessern'
					if schrdirection=='H':
						hInc=None
						vInc=schrweite
					else:
						vInc=None
						hInc=schrweite

					# wir passen vorher die outerBox an
					# wir suchen uns all jene pics, deren outerBox mit dem akutellen pic ueberlappt
					findCandsAndAdaptOuterBox(i)

					# beim vergroessern werden die bilder zentriert - aber jedes x-te mal nicht
					if not s.picsOnPage[i].increaseSize(pHInc=hInc,pWInc=vInc):
						# vergroesserung um gegebenen betrag hat nicht funktioniert - zuruecksetzen
						s.picsOnPage=picsOnPage_bak
						# wir merken uns den schlawiner
						collisionIndex=i
						break
					else:
						# bild positionieren
						modus='C'
						if s.algo=='PO1':
							if schrweite <=2:
								modus='O'
							elif schrweite <=8:
								modus='B'
						s.picsOnPage[i].positionInnerBox(pModus=modus,pOffset=schrweite)

				# alternierend wir einmal horizontal und einmal vertikal vergroessert
				schrdirection='D' if schrdirection=='H' else 'H'
				#return
			schrweite=schrweite//2
#			if firstReduction:
#				# bei der ersten kollision (die bilder sind jetzt hinreichend gross) wird die liste der bilder mit ihren nachbarn angelegt
#				for i,p in enumerate(s.picsOnPage):
#					d={}
#					for j in ('O','U','R','L'):
#						try:
#							# ... die verwendung des hash-values verhindert probleme beim deep-copy ...
#							# wir muessen uns nicht alle bilder anschauen, sondern nur die, wo die outerBoxes overlaps haben
#							d[j]=s.picsOnPage[i].findNeighbours(Side(j),s.picsOnPage[i].getOuterBoxOverlaps())[0]
#						except IndexError:
#							pass
#					s.neighbours[hash(s.picsOnPage[i])]=d
#				firstReduction=False
			
			#print "A - s.picsOnPage: ",  s.picsOnPage,'currPic',s.picsOnPage[i]
		#s.findOverlaps()
		s.findPositionError()

#		return

		# jetzt werden alle bilder, wo's noch moeglich ist, auf's maximum vergroessert ...
		picIndL=range(0, len(s.picsOnPage))
		random.shuffle(list(picIndL))
		cnt=0
		for i in picIndL:
			# wir geben den bildern ein kennzeichen
			cnt=cnt+1
			s.picsOnPage[i].addText(str(cnt))
			# wir passen vorher die outerBox an
			# wir suchen uns all jene pics, deren outerBox mit dem akutellen pic ueberlappt
			findCandsAndAdaptOuterBox(i)

#			if s.picsOnPage[i].spazi():
				# es gibt genug platz fuer eine vergroesserung
				# maximieren
			s.picsOnPage[i].maximizeSize()
				#s.picsOnPage[i].positionInnerBox( pCentered=True)
			#print "B - s.picsOnPage: ",  s.picsOnPage,'currPic',s.picsOnPage[i]


		# fuer poster ...
		randomCorners=random.choice([['LO','RU'],['LU','RO']])
		random.shuffle(randomCorners)

		# jetzt werden alle bilder abschliessend positioniert
		#for i,p in enumerate(s.picsOnPage):
		random.shuffle(list(picIndL))
		for i in picIndL:
			# wir passen vorher die outerBox an
			# wir suchen uns all jene pics, deren outerBox mit dem akutellen pic ueberlappt
			findCandsAndAdaptOuterBox(i)

			if s.algo=='PO1':
				# positionierung bei poster: ChessMatrix wurde das Bild mit einer Farbe getagged (B/W)
				# das koennen wir ausnuetzen um die bilder abwechselnd zu positionieren
				s.picsOnPage[i].positionInnerBox(pModus='D',pLROU=randomCorners[0] if s.picsOnPage[i].chessMatrixColor=='B' else randomCorners[1])
			else:
				# wir versuchen uns an den nachbarn zu orientieren, um festzustellen, wie das bild positioniert werden soll ...
				posDirections=[]

				# wie schauen uns in der liste der nachbarn die vertikalen und horizontalen nachbarn an.
				# bei den vertikalen nachbarn schauen wir, ob ein bild horizontal orientiert ist - wenn ja, uebernehmen wir
				# die erste orientierung die wir finden
				# beu den horizontalen nachbarn uebernehmen wir die erste vertikale orientierung die wir finden
				vFlag=False
				hFlag=False
				try:
					picNeighbourD=s.neighbours[hash(s.picsOnPage[i])]
				except KeyError:
					picNeighbourD={}
					
				# positionierung bei album: wir versuchen uns an den nachbarbildern zu orientieren ...
				for d in picNeighbourD.keys():
					if d in ['O','U'] and not vFlag:
						if 'L' in picNeighbourD[d].posStr:
							posDirections.append(Side('L'))
							vFlag=True
						if 'R' in picNeighbourD[d].posStr:
							posDirections.append(Side('R'))
							vFlag=True
					if d in ['L','R'] and not hFlag:
						if 'O' in picNeighbourD[d].posStr:
							posDirections.append(Side('O'))
							hFlag=True
						if 'U' in picNeighbourD[d].posStr:
							posDirections.append(Side('U'))
							hFlag=True
					s.picsOnPage[i].positionInnerBox(pModus='D',pLROU=[str(x) for x in posDirections])
						

		# und nach dem abschliessenden positionieren noch mal vergroessern - zur sicherheit
		picIndL=range(0, len(s.picsOnPage))
		random.shuffle(list(picIndL))
		for i in picIndL:
			# wir passen vorher die outerBox an
			# wir suchen uns all jene pics, deren outerBox mit dem akutellen pic ueberlappt
			findCandsAndAdaptOuterBox(i)
			s.picsOnPage[i].maximizeSize(pCentered=False)

		#s.findOverlaps()
#		s.findPositionError()

	def adaptOuterBox(s,currPic,pPicL):
		""""
		wir bekommen eine liste von bildern an deren innerBoxes wir die outerBox des aktuellen bildes ausrichten
		muessen.
		idee: implementierung als genetischer algorithmus - der beste kandidat ist jener, wo sich die
		aktuelle innerBox am besten optimieren laesst (proportionen!)
		datenstruktur:
		zuerst bauen wir aus der pic-liste folgende datenstruktur auf:
		von allen innerBoxes der beteiligten pics die der der aktuellen innerBox zugeordnete seite.
		rekursiver algorithmus:
		reihum (o,l,u,r) und rekursiv die aktuelle inner-box ausdehnen, bis es nicht mehr geht (abbruchbedingung) -
		entstandene outerBox in kandidatenliste einfügen
		"""
		# rekursive funktion
		def rekFunc(pBox,pDirection, pDirL,countD):
#			print ("rekFunc(): countD="+str(countD))
# TO BE REFCTORED !! #######################################################################
			#print 'rekFunc',pBox,pDirection
			# faktor fuer vergleiche
			if pDirection in ['L','U']:
				faktor=-1
				reve=True
			else:
				faktor=1
				reve=False
			#versuche pBox in die richtung auszudehnen
			# wir suchen die das naechste level
			#print 'recFunc - try:ausdehnen'
			# ?????????????????????
			# wir suchen den ersten kandidaten der nicht in innerhalb der box liegt
			# warum werden hier keine overlaps berücksichtigt??
			while sideD[pDirection].len() > countD[pDirection] and pBox.getEdge(Side(pDirection)).level()*faktor>=sideD[pDirection].getNth(countD[pDirection], reve).getLevel()*faktor:
#				print ("rekFunc(): countD="+str(countD))
				#print 'recFunc - while:',pBox.getEdge(Side(pDirection)),'>',sideD[pDirection].getNth(countD[pDirection], reve)
				if sideD[pDirection].getNth(countD[pDirection], reve).overlap(pBox.getEdge(Side(pDirection))):
					# abbruchbedingung: wenn sich die linien ueberlappen brechen wir ab
					#print 'rekFunc - abgebrochen
					return
				else:
					# sonst gehen wir eine linie weiter
					countD[pDirection]=countD[pDirection]+1
				# entfernen der side aus der liste
				#sideD[pDirection]=sideD[pDirection][1:]
			try:
				# weiter ausdehnen bis wir anstehen
				# wir suchen von dem kandidaten ausgehend, die erste linie mit overlap
				while not sideD[pDirection].getNth(countD[pDirection], reve).overlap(pBox.getEdge(Side(pDirection))):
					countD[pDirection]=countD[pDirection]+1
			except IndexError:
				# das letzte element der liste
				countD[pDirection]=sideD[pDirection].len()-1

			# jetzt sind wir beim kandidaten angekommen
			# wir vergroessern die box entsprechend
			pBox.setBoxFromLevels({pDirection:sideD[pDirection].getNth(countD[pDirection], reve).getLevel()})
			#print 'recFunc - candL.append seite:',sideD[pDirection].getNth(countD[pDirection], reve),{pDirection:sideD[pDirection].getNth(countD[pDirection], reve).getLevel()}
			#print 'recFunc - candL.append box:',pBox
			candS.add(pBox)

			# rekursiver aufruf von rekFunc in alle richtungen, ausser der aktuellen

			pDirL.remove(pDirection)
			for d in pDirL:
				rekFunc(copy.deepcopy(pBox),d,copy.deepcopy(pDirL), copy.deepcopy(countD))
		# ende der funktion ##############
#		debug_boxestakeninaccount=[]
		#print 'adaptOuterBox',currPic,pPicL
		# aufbau der datenstruktur (eine innerBox kann auch maximal 2 seiten beitragen)
		sideD={'L':LinesOnLevelStore(),'R':LinesOnLevelStore(),'O':LinesOnLevelStore(),'U':LinesOnLevelStore()}
		for p in pPicL:
#			debug_boxestakeninaccount.append(p.innerBox)
			if currPic.getEdge(Side('L')).level()>=p.getEdge(Side('R')).level():
				sideD['L'].add(p.getEdge(Side('R')))
			if  currPic.getEdge(Side('R')).level()<=p.getEdge(Side('L')).level():
				sideD['R'].add(p.getEdge(Side('L')))
			if  currPic.getEdge(Side('O')).level()<=p.getEdge(Side('U')).level():
				sideD['O'].add(p.getEdge(Side('U')))
			if  currPic.getEdge(Side('U')).level()>=p.getEdge(Side('O')).level():
				sideD['U'].add(p.getEdge(Side('O')))
		# wir fuegen noch die seitenraender dazu (dann brauchen wir in rekFunc() kein except)
#		debug_boxestakeninaccount.append(s.pageBox)
		sideD['L'].add(s.pageBox.getEdge(Side('L')))
		sideD['R'].add(s.pageBox.getEdge(Side('R')))
		sideD['O'].add(s.pageBox.getEdge(Side('O')))
		sideD['U'].add(s.pageBox.getEdge(Side('U')))

		#print 'sideD: ',sideD

		#kandidatenliste
		candS=BoxStore()

#		#iteratorendictionary ...
#		iterD={'L':iter(sideD['L'].iterMe(reverse=True)), \
#		           'R':iter(sideD['R'].iterMe(reverse=True)),\
#				   'O':iter(sideD['O'].iterMe(reverse=True)),\
#				   'U':iter(sideD['U'].iterMe(reverse=True))}

		# die startbox beinhaltet den zwischenabstand
		startBox=copy.deepcopy(currPic.innerBox)
#		startBox.x=startBox.x-s.dist
#		startBox.y=startBox.y-s.dist
#		startBox.h=startBox.h+2*s.dist
#		startBox.w=startBox.w+2*s.dist
		# finden wir sonst keinen kandidaten, ist der einzige verbleibende kandidat immer noch die startbox
		candS.add(startBox)
		# wir bauen die kandidatenliste rekursiv auf
		rekFunc(copy.deepcopy(startBox),'L',['L', 'R', 'O', 'U'],{'L':0, 'R':0, 'O':0, 'U':0})
		rekFunc(copy.deepcopy(startBox),'R',['L', 'R', 'O', 'U'], {'L':0, 'R':0, 'O':0, 'U':0})
		rekFunc(copy.deepcopy(startBox),'O',['L', 'R', 'O', 'U'], {'L':0, 'R':0, 'O':0, 'U':0})
		rekFunc(copy.deepcopy(startBox),'U',['L', 'R', 'O', 'U'], {'L':0, 'R':0, 'O':0, 'U':0})

		candL=candS.get()
#		debug_candL=candL
		#print 'candL: ',candL

		if candL==[]:
			# anscheinend kann das passieren - warum wissen wir nicht ...
			return

		# jetzt bewerten wir unsere kandidatenboxen und waehlen die neue outerBox aus
		candSizeL=[]
		for cand in candL:
			# wir probieren's jeweils in der horizontale und vertikale
			# wir berechnen anhand des gegebenen kandidaten die seiten des Pics (unter beibehaltung der proportionen)
			# und zwar fuer W und fuer H - und waehlen dann jene groesse, wo das PIC nicht groesser als der kandidat ist.
			new_w=int(round(currPic.w()*(float(cand.h)/currPic.h())))
			new_h=int(round(currPic.h()*(float(cand.w)/currPic.w())))
			if new_w>cand.w:
				size=new_h*cand.w
			else:
				size=new_w*cand.h
			candSizeL.append((cand, size))

		# absteigend nach der groesse sortieren - des Pics und des Kandidaten
		#candSizeL.sort(key=lambda x: x[1],reverse=True)
		candSizeL.sort(key=itemgetter(1),reverse=True)
		
		# jetzt haben wir die neue outerBox gefunden
		#print 'new outerBox: ',candSizeL[0][0]
		currPic.setOuterBox(candSizeL[0][0])
#		debug_newouterbox=candSizeL[0][0]
		# setzen der borderL
		borderL=[]
		# koennten wir im folgenden nicht einfach die borderL der alten box wiederverwenden????????
		for side in (Side('O'),Side('U'),Side('R'),Side('L')):
			if currPic.outerBox.getEdge(side).level()==s.pageBox.getEdge(side).level():
				borderL.append(side)
		currPic.outerBox.setBorders(borderL)

#		for p in  pPicL:
#			if debug_newouterbox.intersecting(p.innerBox, pTouchOnly=False):
#				print "adaptOuterBox Error Start"
#				print "Overlap: ",debug_newouterbox, p.innerBox
#				print "CandList: ",debug_candL
#				print "BoxesLookedAt: ",debug_boxestakeninaccount
#				print "CurrPic: ",currPic
#				print "AllPics: ", s.picsOnPage
#				print "adaptOuterBox Error End"
#				x=1/0

	def fillWindow(s):
		"""
		ein window ist ist die liste von bildern die zur erstellung einer
		seite in betracht gezogen wird. (koennte parametrisiert werden)
		Hier wird diese Anzahl Bilder in eine eigene Liste geladen

		Bei der Erstellung der Bilderliste wird jedem Bild ausserdem ein
		Timebucket zugewiesen (d.h. ein Tupel Bld/TimeBucket) -  das ist ein zusaetzliches Sortierkriterium
		und ist ein Mass dafuer, dass die Bilder mit dem gleichen Timebucket
		innerhalb einer bestimmten Zeit aufgenommen wurden
		"""
		s.logdbg(inspect.currentframe())

		#print 'fillWindow() - winSize: ',s.winSize
		s.windowL=[[x, None] for x in s.picL[0:s.winSize]]
		#print 'fillWindow() - windowL: ',s.windowL

		# finde kleinsten zeitstempel
		timestamp=None
		for p in [x[0] for x in s.windowL]:
			if p.getDateTime()!=None:
				#print p.getDateTime()
				if timestamp==None:
					timestamp=p.getDateTime()
				else:
					if timestamp > p.getDateTime():
						timestamp=p.getDateTime()
		#print 'timestamp=',timestamp

		# setzen der timeBuckets
		if timestamp!=None:
			bucketsize=gParGet('bucketsize') # in sekunden
			for i,x in enumerate(s.windowL):
				try:
					td=s.windowL[i][0].getDateTime()-timestamp
					s.windowL[i][1]=(td.days*24*60*60+td.seconds)//bucketsize
				except TypeError:
					# wenn das bild keinen timestamp hat machen wir nix
					pass



	def initOuterBoxes(s):
		"""
		hier werden bei allen Pic-objekten die outerBoxes initialisiert
		wir berechnen die 'levels' der outerBox und uebergeben das sich ergebende
		dictionary der entsprechenden init-prozedur des box-Objekts

		Todo: wir docken an kanten an, die uns wurscht sein sollten (???)
		"""
		s.logdbg(inspect.currentframe())

		for i,p in enumerate(s.picsOnPage):
			outerBoxLevels={}
			borders=[]
			for side in [Side('L'),Side('R'),Side('O'),Side('U')]:
				try:
					# das ist ein etwas gewagter schritt, wie wir uns den abstand ausrechenen
					outerBoxLevels[str(side)]=s.picsOnPage[i].findNeighbours(side,s.picsOnPage)[0].getEdge(side.opposite()).level()
				except IndexError:
					#hier brauchen wir die seitenraender
					if str(side)=='L' or str(side)=='U':
						# wir gehen vom seitenrand aus, zuehen aber s.dist ab, d.h. beim justieren der bilder
						# gehen sie nicht ueber den seitenrand hinaus, wir muessen aber in der Pic-Klasse
						# nicht gesondert beruecksichtigen
						outerBoxLevels[str(side)]=s.pageDist[str(side)]-s.dist
						#die outerBox bekommt die info, dass sie am rand ist
						borders.append(side) # das bild wird angedockt ...
					elif str(side)=='R':
						outerBoxLevels[str(side)]=s.pagesize[0]-s.pageDist[str(side)]+s.dist
						borders.append(side) # das bild wird angedockt ...
					elif str(side)=='O':
						outerBoxLevels[str(side)]=s.pagesize[1]-s.pageDist[str(side)]+s.dist
						borders.append(side) # das bild wird angedockt ...
			#print 'initOuterBoxes',outerBoxLevels
			s.picsOnPage[i].initOuterBox(outerBoxLevels,borders)

	def chooseNpositionPics(s):
		"""
		bilder fuer seite auswaehlen und grob positionieren
		"""
		s.logdbg(inspect.currentframe())

		s.hotPoints=HotPointCollection('RU-LU')
		pFixHeight=None

		# nach hoehe der bilder ordnen - und nach timebuckets
		try:
			s.windowL.sort(key=lambda x: (x[1]*(-1),x[0].getMinSize()[1]),reverse=True)
		except:
			# sollte kein time-bucket vorhanden sein wird nur nach der groesse sortiert
			s.windowL.sort(key=lambda x: x[0].getMinSize()[1],reverse=True)

		linksunten=Coor(0,0,'LU')
		for p in [x[0] for x in s.windowL]:
			s.loginfo(p.filename)
			tS=(p.w(),p.h())
			# wir merken uns die hoehe fuer's naechste bild ...
			pFixHeight=tS[1]

			# wir checken, ob sich das bild ueberhaupt auf einer seite ausgehen kann, und wenn nicht raise eines fehlers
			# (zur vermeidung von endloslaeufen ...)
			if tS[0]>=s.pagesize[0]-s.pageDist['R']-s.pageDist['L'] or tS[1]>=s.pagesize[1]-s.pageDist['O']-s.pageDist['U']:
				raise AppError(str(tS),'Pic does not fit on page!: ')

			#print 6,linksunten
			hp=s.hotPoints.getNext(linksunten)
			if hp == None:
				hp=Coor(s.pagesize[0]-s.pageDist['R'],s.pageDist['U'])
			# test ob sich das bild noch auf dieser seite ausgeht
			cnt=1
			while hp.getCoor()[0]-tS[0]-s.pageDist['L']<0 or hp.getCoor()[1]+tS[1]+s.pageDist['O']>s.pagesize[1]:
				# wir loopen so lange, bis wir einen platz finden
				s.loginfo('0X: '+str((hp,tS,s.pagesize)))
				cnt=cnt+1
				hp=s.hotPoints.getNext(linksunten,cnt)
				if hp==None:
					# wir haben keinen platz auf der seite gefunden
					break
			if hp != None:
				hp.setCoorPos('RU')
				#p.setPos((linksunten[0]+s.distRough,linksunten[1]),tS)
				eckpunktD=p.setPosition(pCoorObj=hp,pBorders=False,pSize=(None,pFixHeight),pFix=True)
				s.hotPoints.addPoint(eckpunktD['RO']+Coor(0,s.distRough))
				linksunten=eckpunktD['LU']-Coor(s.distRough,0)
				s.hotPoints.addPoint(linksunten)

				s.picsOnPage.append(p)
				# entferne bild aus der orginalbilderliste
				s.picL.remove(p)


	def chooseNpositionPicsT(s):
		"""
		bilder fuer seite auswaehlen und grob positionieren
		"""
		s.logdbg(inspect.currentframe())

		s.hotPoints=HotPointCollection('LO-LU')
		pFixWidth=None

		# nach hoehe der bilder ordnen - und nach timebuckets
		try:
			s.windowL.sort(key=lambda x: (x[1]*(-1),x[0].getMinSize()[0]),reverse=True)
		except:
			# sollte kein time-bucket vorhanden sein wird nur nach der groesse sortiert
			s.windowL.sort(key=lambda x: x[0].getMinSize()[0],reverse=True)

		linksunten=Coor(0,0,'LU')
		for p in [x[0] for x in s.windowL]:
			s.loginfo(p.filename)
			tS=(p.w(),p.h())
			pFixWidth=tS[0]

			# wir checken, ob sich das bild ueberhaupt auf einer seite ausgehen kann, und wenn nicht raise eines fehlers
			# (zur vermeidung von endloslaeufen ...)
			if tS[0]>=s.pagesize[0]-s.pageDist['R']-s.pageDist['L'] or tS[1]>=s.pagesize[1]-s.pageDist['O']-s.pageDist['U']:
				raise AppError(str(tS),'Pic does not fit on page!: ')

			#print 6,linksunten
			hp=s.hotPoints.getNext(linksunten)
			if hp == None:
				hp=Coor(s.pageDist['L'],s.pagesize[1]-s.pageDist['O'])
			# test ob sich das bild noch auf dieser seite ausgeht
			cnt=1
			while hp.getCoor()[1]-tS[1]-s.pageDist['U']<0 or hp.getCoor()[0]+tS[0]+s.pageDist['R']>s.pagesize[0]:
				# wir loopen so lange, bis wir einen platz finden
				s.loginfo('0X: '+str((hp,tS,s.pagesize)))
				cnt=cnt+1
				hp=s.hotPoints.getNext(linksunten,cnt)
				if hp==None:
					# wir haben keinen platz auf der seite gefunden
					break
			if hp != None:
				hp.setCoorPos('LO')
				#p.setPos((linksunten[0],linksunten[1]+s.distRough),tS)
				eckpunktD=p.setPosition(pCoorObj=hp,pBorders=False,pSize=(pFixWidth,None),pFix=True)
				s.hotPoints.addPoint((eckpunktD['RO']+Coor(s.distRough,0)))
				linksunten=eckpunktD['LU']-Coor(0,s.distRough)
				s.hotPoints.addPoint(linksunten)

				s.picsOnPage.append(p)
				# entferne bild aus der orginalbilderliste
				s.picL.remove(p)

	def chooseNpositionPicsBorder(s):
		"""
		dieser stacking algorithmus ordnet eine reihe bilder unten von links nach rechts an
		dann eine reihe bilder oben von rechts nach links.
		"""
		s.logdbg(inspect.currentframe())
		s.windowL.sort(key=lambda x: (x[0]*(-1),x[1].getMinSize()[1]),reverse=True)

		linksunten=Coor(gParGet('pageDist')['L']-s.distRough, gParGet('pageDist')['U']-s.distRough, 'LU')
		rechtsoben=Coor(s.pagesize[0]-gParGet('pageDist')['R']+s.distRough, s.pagesize[1]-gParGet('pageDist')['O']+s.distRough,'RO')
		sem=0
		fixHeight=[0,0]
		for p in [x[0] for x in s.windowL]:
			# wir checken, ob sich das bild ueberhaupt auf einer seite ausgehen kann, und wenn nicht raise eines fehlers
			# (zur vermeidung von endloslaeufen ...)
			if p.w()>=s.pagesize[0]-s.pageDist['R']-s.pageDist['L'] or p.h()>=s.pagesize[1]-s.pageDist['O']-s.pageDist['U']:
				raise AppError(str(p.w())+','+str(p.h()),'Pic does not fit on page!: ')
			if sem%2==0:
				# unten
				if linksunten.getCoor()[0]+p.w()<=s.pagesize[0]-gParGet('pageDist')['R'] and \
					linksunten.getCoor()[1]+p.h()<=s.pagesize[1]-gParGet('pageDist')['O']:
					# pruefen ob sich bild ausgeht
					eckpunktD=p.setPosition(pCoorObj=linksunten, pBorders=True,pSize=(None,fixHeight[sem]),pFix=True) #positionieren
					# auf overlaps checken
					overlap=False
					for q in s.picsOnPage:
						tmpBox=q.innerBox.getEnlargedBox(s.dist)
						if p.innerBox.intersecting(tmpBox,pTouchOnly=False):
							overlap=True
							break
					if overlap==False:
						# bild auf seite registrieren
						s.picsOnPage.append(p)
						# entferne bild aus der orginalbilderliste
						s.picL.remove(p)

						# linksunten neu setzen
						linksunten.setCoor(pX=eckpunktD['RU'].getCoor()[0])
						# die hoehe des bildes merken
						fixHeight[sem]=p.h()

						sem=(sem+1)%2
					else:
						p.clearPosition()
			else:
				# oben
				if rechtsoben.getCoor()[0]-p.w()>=0+gParGet('pageDist')['L'] and \
					rechtsoben.getCoor()[1]-p.h()>=0+gParGet('pageDist')['U']:
					# pruefen ob sich bild ausgeht
					eckpunktD=p.setPosition(pCoorObj=rechtsoben, pBorders=True,pSize=(None,fixHeight[sem]),pFix=True) #positionieren
					# auf overlaps checken
					overlap=False
					for q in s.picsOnPage:
						tmpBox=q.innerBox.getEnlargedBox(s.dist)
						if p.innerBox.intersecting(tmpBox,pTouchOnly=False):
							overlap=True
							break
					if overlap==False:
						# bild auf seite registrieren
						s.picsOnPage.append(p)
						# entferne bild aus der orginalbilderliste
						s.picL.remove(p)
						# linksunten neu setzen
						rechtsoben.setCoor(pX=eckpunktD['LO'].getCoor()[0])
						# die hoehe des bildes merken
						fixHeight[sem]=p.h()

						sem=(sem+1)%2
					else:
						p.clearPosition()


	def chooseNpositionPicsOpposedDirection(s):
		"""
		dieser stacking algorithmus ist eine Kombination von chooseNpositionPics() und chooseNpositionPicsBorder():
		gegenläifig von rechts unten und links oben wird die seite mit bildern gefuellt ...
		"""
		s.logdbg(inspect.currentframe())
		#print 's.windowL',s.windowL
		try:
			s.windowL.sort(key=lambda x: (x[1]*(-1),x[0].getMinSize()[1]),reverse=True)
		except:
			# sollte kein time-bucket vorhanden sein wird nur nach der groesse sortiert
			s.windowL.sort(key=lambda x: x[0].getMinSize()[1],reverse=True)

		hpCollU=HotPointCollection('RU-LU')
		hpCollO=HotPointCollection('LO-RO')


		linksunten=Coor(gParGet('pageDist')['L']-s.distRough, gParGet('pageDist')['U']-s.distRough, 'LU')
		rechtsoben=Coor(s.pagesize[0]-gParGet('pageDist')['R']+s.distRough, s.pagesize[1]-gParGet('pageDist')['O']+s.distRough,'RO')
		sem=0
		fixHeight=[0,0]

		for p in [x[0] for x in s.windowL]:
			# wir checken, ob sich das bild ueberhaupt auf einer seite ausgehen kann, und wenn nicht raise eines fehlers
			# (zur vermeidung von endloslaeufen ...)
			if p.w()>=s.pagesize[0]-s.pageDist['R']-s.pageDist['L'] or p.h()>=s.pagesize[1]-s.pageDist['O']-s.pageDist['U']:
				print ('ERROR!',p,p.w(),s.pagesize[0]-s.pageDist['R']-s.pageDist['L'],p.h(),s.pagesize[1]-s.pageDist['O']-s.pageDist['U'])
				raise AppError(str(p.w())+','+str(p.h()),'Pic does not fit on page!: ')
			if sem%2==0:
				# unten

				hp=hpCollU.getNext(linksunten)
				if hp == None:
					hp=Coor(s.pagesize[0]-s.pageDist['R'],s.pageDist['U'])
				# test ob sich das bild noch auf dieser seite ausgeht
				cnt=1
				while hp.getCoor()[0]-p.w()-s.pageDist['L']<0 or hp.getCoor()[1]+p.h()+s.pageDist['O']>s.pagesize[1]:
					# wir loopen so lange, bis wir einen platz finden
					#s.loginfo('0X: '+str((hp,tS,s.pagesize)))
					cnt=cnt+1
					hp=hpCollU.getNext(linksunten,cnt)
					if hp==None:
						# wir haben keinen platz auf der seite gefunden
						break
				if hp != None:
					hp.setCoorPos('RU')
					#p.setPos((linksunten[0]+s.distRough,linksunten[1]),tS)
					eckpunktD=p.setPosition(pCoorObj=hp,pBorders=False,pSize=(None,fixHeight[sem]),pFix=True)

					# auf overlaps checken
					overlap=False
					for q in s.picsOnPage:
						tmpBox=q.innerBox.getEnlargedBox(s.dist)
						if p.innerBox.intersecting(tmpBox,pTouchOnly=False):
							overlap=True
							break
					if overlap==False:
						# bild auf seite registrieren
						s.picsOnPage.append(p)
						# entferne bild aus der orginalbilderliste
						s.picL.remove(p)

						# hp-collection befuellen
						hpCollU.addPoint(eckpunktD['RO']+Coor(0,s.distRough))
						linksunten=eckpunktD['LU']-Coor(s.distRough,0)
						hpCollU.addPoint(linksunten)
						# die hoehe des bildes merken
						fixHeight[sem]=p.h()

						sem=(sem+1)%2
					else:
						p.clearPosition()
			else:
				# oben

				hp=hpCollO.getNext(rechtsoben)
				if hp == None:
					hp=Coor(s.pageDist['L'],s.pagesize[1]-s.pageDist['O'])
				# test ob sich das bild noch auf dieser seite ausgeht
				cnt=1
				while hp.getCoor()[0]+p.w()+s.pageDist['R']>s.pagesize[0] or hp.getCoor()[1]-p.h()-s.pageDist['U']<0:
					# wir loopen so lange, bis wir einen platz finden
					#s.loginfo('0X: '+str((hp,tS,s.pagesize)))
					cnt=cnt+1
					hp=hpCollO.getNext(rechtsoben,cnt)
					if hp==None:
						# wir haben keinen platz auf der seite gefunden
						break
				if hp != None:
					hp.setCoorPos('LO')
					#p.setPos((linksunten[0]+s.distRough,linksunten[1]),tS)
					eckpunktD=p.setPosition(pCoorObj=hp,pBorders=False,pSize=(None,fixHeight[sem]),pFix=True)

					# auf overlaps checken
					overlap=False
					for q in s.picsOnPage:
						tmpBox=q.innerBox.getEnlargedBox(s.dist)
						if p.innerBox.intersecting(tmpBox,pTouchOnly=False):
							overlap=True
							break
					if overlap==False:
						# bild auf seite registrieren
						s.picsOnPage.append(p)
						# entferne bild aus der orginalbilderliste
						s.picL.remove(p)

						# hp-collection befuellen
						hpCollO.addPoint(eckpunktD['LU']-Coor(0,s.distRough))
						rechtsoben=eckpunktD['RO']+Coor(s.distRough,0)
						hpCollO.addPoint(rechtsoben)
						# die hoehe des bildes merken
						fixHeight[sem]=p.h()

						sem=(sem+1)%2
					else:
						p.clearPosition()
		#print 'hpCollO',hpCollO.getList()

	def chooseNpositionPicsOpposedDirectionT(s):
		"""
		dieser stacking algorithmus ist eine Kombination von chooseNpositionPics() und chooseNpositionPicsBorder():
		gegenläifig von rechts unten und links oben wird die seite mit bildern gefuellt ...
		"""
		s.logdbg(inspect.currentframe())
		try:
			s.windowL.sort(key=lambda x: (x[1]*(-1),x[0].getMinSize()[1]),reverse=True)
		except:
			# sollte kein time-bucket vorhanden sein wird nur nach der groesse sortiert
			s.windowL.sort(key=lambda x: x[0].getMinSize()[1],reverse=True)

		hpCollU=HotPointCollection('LO-LU')
		hpCollO=HotPointCollection('RU-RO')


		linksunten=Coor(gParGet('pageDist')['L']-s.distRough, gParGet('pageDist')['U']-s.distRough, 'LU')
		rechtsoben=Coor(s.pagesize[0]-gParGet('pageDist')['R']+s.distRough, s.pagesize[1]-gParGet('pageDist')['O']+s.distRough,'RO')
		sem=0
		fixHeight=[0,0]

		for p in [x[0] for x in s.windowL]:
			# wir checken, ob sich das bild ueberhaupt auf einer seite ausgehen kann, und wenn nicht raise eines fehlers
			# (zur vermeidung von endloslaeufen ...)
			if p.w()>=s.pagesize[0]-s.pageDist['R']-s.pageDist['L'] or p.h()>=s.pagesize[1]-s.pageDist['O']-s.pageDist['U']:
				print ('ERROR!',p,p.w(),s.pagesize[0]-s.pageDist['R']-s.pageDist['L'],p.h(),s.pagesize[1]-s.pageDist['O']-s.pageDist['U'])
				raise AppError(str(p.w())+','+str(p.h()),'Pic does not fit on page!: ')
			if sem%2==0:
				# links oben -> links unten

				hp=hpCollU.getNext(linksunten)
				if hp == None:
					hp=Coor(s.pageDist['L'],s.pagesize[1]-s.pageDist['O'])
				# test ob sich das bild noch auf dieser seite ausgeht
				cnt=1
				while hp.getCoor()[1]-p.h()-s.pageDist['U']<0 or hp.getCoor()[0]+p.w()+s.pageDist['R']>s.pagesize[0]:
					# wir loopen so lange, bis wir einen platz finden
					#s.loginfo('0X: '+str((hp,tS,s.pagesize)))
					cnt=cnt+1
					hp=hpCollU.getNext(linksunten,cnt)
					if hp==None:
						# wir haben keinen platz auf der seite gefunden
						break
				if hp != None:
					hp.setCoorPos('LO')
					#p.setPos((linksunten[0]+s.distRough,linksunten[1]),tS)
					eckpunktD=p.setPosition(pCoorObj=hp,pBorders=False,pSize=(fixHeight[sem],None),pFix=True)

					# auf overlaps checken
					overlap=False
					for q in s.picsOnPage:
						tmpBox=q.innerBox.getEnlargedBox(s.dist)
						if p.innerBox.intersecting(tmpBox,pTouchOnly=False):
							overlap=True
							break
					if overlap==False:
						# bild auf seite registrieren
						s.picsOnPage.append(p)
						# entferne bild aus der orginalbilderliste
						s.picL.remove(p)

						# hp-collection befuellen
						hpCollU.addPoint(eckpunktD['RO']+Coor(s.distRough,0))
						linksunten=eckpunktD['LU']-Coor(0,s.distRough)
						hpCollU.addPoint(linksunten)
						# die hoehe des bildes merken
						fixHeight[sem]=p.w()

						sem=(sem+1)%2
					else:
						p.clearPosition()
			else:
				# rechts unten -> rechts oben

				hp=hpCollO.getNext(rechtsoben)
				if hp == None:
					hp=Coor(s.pagesize[0]-s.pageDist['R'],s.pageDist['U'])
				# test ob sich das bild noch auf dieser seite ausgeht
				cnt=1
				while hp.getCoor()[1]+p.h()+s.pageDist['O']>s.pagesize[1] or hp.getCoor()[0]-p.w()-s.pageDist['L']<0:
					# wir loopen so lange, bis wir einen platz finden
					#s.loginfo('0X: '+str((hp,tS,s.pagesize)))
					cnt=cnt+1
					hp=hpCollO.getNext(rechtsoben,cnt)
					if hp==None:
						# wir haben keinen platz auf der seite gefunden
						break
				if hp != None:
					hp.setCoorPos('RU')
					#p.setPos((linksunten[0]+s.distRough,linksunten[1]),tS)
					eckpunktD=p.setPosition(pCoorObj=hp,pBorders=False,pSize=(fixHeight[sem],None),pFix=True)

					# auf overlaps checken
					overlap=False
					for q in s.picsOnPage:
						tmpBox=q.innerBox.getEnlargedBox(s.dist)
						if p.innerBox.intersecting(tmpBox,pTouchOnly=False):
							overlap=True
							break
					if overlap==False:
						# bild auf seite registrieren
						s.picsOnPage.append(p)
						# entferne bild aus der orginalbilderliste
						s.picL.remove(p)

						# hp-collection befuellen
						hpCollO.addPoint(eckpunktD['LU']-Coor(s.distRough,0))
						rechtsoben=eckpunktD['RO']+Coor(0,s.distRough)
						hpCollO.addPoint(rechtsoben)
						# die hoehe des bildes merken
						fixHeight[sem]=p.w()

						sem=(sem+1)%2
					else:
						p.clearPosition()
		#print 'hpCollO',hpCollO.getList()
	
	
	def positionPoster(s):
		"""
		positionierungsalgorithmus fuer poster - d.h. es gibt nur eine seite und alle bilder
		kommen da drauf
		annahme: der poster ist quadratisch
		ablauf:
		* "maximierten" proportionen eines bildes ausrechnen
		* die n*m-proportionen der matrix berechnen
		* die bilder provisorisch am poster anordnen (Achtung: dabei wird auch minDiagonale des pics gesetzt)
		"""
		s.logdbg(inspect.currentframe())

		# berechnen der maximierten proportionen
		hMax=0
		wMax=0
		for p in s.picL:
			if p.h()>hMax:
				hMax=p.h()
			if p.w()>wMax:
				wMax=p.w()
		hMax=hMax+s.distRough
		wMax=wMax+s.distRough

		# berechnen der n*m-proportionen der matrix
		area=0
		picLlen=len(s.picL)
		wPage=s.pagesize[0]-s.pageDist['L']-s.pageDist['R']
		hPage=s.pagesize[1]-s.pageDist['O']-s.pageDist['U']
		for n in range (1, picLlen+1):
			m=picLlen//n
			if picLlen%n>0:
				m=m+1
			w1=n*wMax
			h1=m*hMax
			# proportional in seite einpassen
			w2=wPage
			h2=int(round((float(h1)/w1)*w2))
			if h2>hPage:
				h2=hPage
				w2=int(round((float(w1)/h1)*h2))
			# flaeche einzelnen bildes ausrechnen
			w3=w2//n
			h3=h2//m
			# flaeche berechnen
			print ('!', n, m,h3, w3,   h3*w3*len(s.picL))
			if h3*w3*len(s.picL)>area:
				area=h3*w3*len(s.picL)
				nO=n
				mO=m
			else:
				# wir haben das maximum erreicht, wir rechnen mit mO und nO
				break
		#print '!!', nO, mO

		wO=int(round(wPage/float(nO)))
		hO=int(round(hPage/float(mO)))

		#print 'pagesize:', s.pagesize
		#print  'wPage, hPage:', wPage, hPage
		#print  'nO, mO:', nO, mO
		#print 'hO, wO:', hO, wO

#		# auffuellen der liste auf n*m
#		matriX=range(0,picLlen)+[None]*(nO*mO-picLlen)
#		# mischen
#		random.shuffle(matriX)
		
		# abhaengig von der orientierung erstellen wir 2 getrennte listen von bildern
		pL=[x for x in s.picL if x.getOrientation()=='P']		# Portrait
		lL=[x for x in s.picL if x.getOrientation()=='L']		# Landscape
		if len(pL)<len(lL):
			l1=pL
			l2=lL
		else:
			l2=pL
			l1=lL
		
		matObj=ChessMatrix(mO, nO)
		# zuerst die luecken
		matObj.fillGaps(nO*mO-picLlen)
		# dann die kuerzere liste
		matObj.fill(l1)
		# die laengere liste zum schluss
		matObj.fill(l2)
#		matriX=matObj.getList()
		matriX=matObj.get()
		
#		print 'matriX: ', matriX

		#provisorische anordnung der bilder
#		for j, col in enumerate(matriX):
#			for i, e in enumerate(col):
#				try:
#					# berechnen der minDiagonale als 1/2 der diagonale von wO und hO
#					#e['pic'].setMinDiagonal(round(pow(pow(wO,2)+pow(hO,2),0.5)*1/2))
#					e['pic'].setMinDiagonal(round(((wO**2+hO**2)**0.5)*1/2))
#					centerP=Coor(s.pageDist['L']+int(round(wO/2.0))+wO*i, s.pageDist['U']+int(round(hO/2.0))+hO*j)
#					eckpunktD=e['pic'].setPosition(pCoorObj=centerP,pBorders=False)
#					s.picsOnPage.append(e['pic'])
#				except AttributeError:
#					# luecke
#					pass
		# das ist ein DIRTY HACK
		# die Idee ist, dass die Luecken fuer's layout schlecht sind, und deshalb werden in den Zeilen, wo Luecken vorkommen, die Bilder zusammengerueckt
		# das heisst, wir filtern in jeder Zeile i alle Gaps raus -> picLst und berechnen wO neu -> wOcurr
		# diese Funktionalitaet koennte man der ChessMatrix beibringen - und es sollte auch nicht immer zeilenorientiert sein (sondern auch spaltenorientiert)
		for j, col in enumerate(matriX):
			#print "col",col
			picLst=[]
			for i, e in enumerate(col):
				if e['gap']!=2:
					picLst.append(e)
			#print "picLst",picLst
			wOcurr=int(round(wPage/float(len(picLst))))
			for i, e in enumerate(picLst):
#				try:
					# berechnen der minDiagonale als 1/2 der diagonale von wO und hO
					e['pic'].setMinDiagonal(round(((wO**2+hO**2)**0.5)*0.3))
					centerP=Coor(s.pageDist['L']+int(round(wOcurr/2.0))+wOcurr*i, s.pageDist['U']+int(round(hO/2.0))+hO*j)
					eckpunktD=e['pic'].setPosition(pCoorObj=centerP,pBorders=False)
					s.picsOnPage.append(e['pic'])
				

	def explode(s):
		"""
		bilder positionieren und auf maximalgroesse bringen
		(unter einhatlung des mindestabstandes (parametrisieren!))
		was: ruecke alle bilder die eine seite zum rand haben an den rand
		"""
		s.logdbg(inspect.currentframe())

		#print 'explode1'

		for i,p in enumerate(s.picsOnPage):
			#print 'explode2',p
			for side in [Side('L'),Side('R'),Side('O'),Side('U')]:
				#print 'explode3',side
				if p.findNeighbours(side,s.picsOnPage)==[]:
					#print 'explode4: no neighbour'

					#logging.info(str(("loop",side,s.findNeighbours(p,side))))
					# ruecke das bild an den entsprechenden rand der seite
					if str(side)=='L':
						#logging.info('L')
						#s.picsOnPage[i].setPos((s.pageDist['L'],None))
						coor=Coor(s.pageDist['L'],p.y(),'LU')
						s.picsOnPage[i].setPosition(pCoorObj=coor)
					elif str(side)=='R':
						#logging.info('R')
						#s.picsOnPage[i].setPos((s.pagesize[0]-s.picsOnPage[i].w()-s.pageDist['R'],None))
						coor=Coor(s.pagesize[0]-s.pageDist['R'],p.y(),'RU')
						s.picsOnPage[i].setPosition(pCoorObj=coor)
					elif str(side)=='U':
						#logging.info('U')
						#s.picsOnPage[i].setPos((None,s.pageDist['U']))
						coor=Coor(p.x(),s.pageDist['U'],'LU')
						s.picsOnPage[i].setPosition(pCoorObj=coor)
					elif str(side)=='O':
						#logging.info('O')
						#s.picsOnPage[i].setPos((None,s.pagesize[1]-s.picsOnPage[i].h()-s.pageDist['O']))
						coor=Coor(p.x(),s.pagesize[1]-s.pageDist['O'],'LO')
						s.picsOnPage[i].setPosition(pCoorObj=coor)
					else:
						s.logerr('keine Seite passt!!')  # das sollt' eigentlich nicht passieren ...

	def transform(s,pTransform):
		"""
		hier wird die seite vertikal und/oder horizontal gespiegelt
		"""
		if 'H' in pTransform:
			for i,p in enumerate(s.picsOnPage):
				s.picsOnPage[i].set_x(s.pagesize[0]-s.picsOnPage[i].x()-s.picsOnPage[i].w())
		if 'V' in pTransform:
			for i,p in enumerate(s.picsOnPage):
				s.picsOnPage[i].set_y(s.pagesize[1]-s.picsOnPage[i].y()-s.picsOnPage[i].h())


	def findOverlaps(s):
		"""
		wenn sich auf der seite 2 bilder ueberlappen, geben wir alarm!
		nur fuer debuggingzwecke
		"""
		for i,p in enumerate(s.picsOnPage):
			for j,q in enumerate(s.picsOnPage):
				if j!=i:
					if s.picsOnPage[i].innerBox.intersecting(s.picsOnPage[j].innerBox):
						print ('OVERLAP!!!!!!!!!!!!',s.picsOnPage[i], s.picsOnPage[j])

	def findPositionError(s):
		"""
		wenn bei einem bild die innerBox nicht korrekt in der outerBox positioniert ist geben wir alarm!
		nur fuer debuggingzwecke
		"""
		for i,p in enumerate(s.picsOnPage):
			if not p.checkPositioning():
				print ('POSITION ERROR!!!!!!!!!', p)

	def compr(s,o):
		"""
		vergleich 2er seiten - die summe der flaeche aller bilder
		"""
		areaS=0
		areaO=0
		for p in s.picsOnPage:
			areaS=areaS+p.getArea()

		for p in o.picsOnPage:
			areaO=areaO+p.getArea()

		if areaS<areaO:
			return -1
		elif areaS>areaO:
			return 1
		else:
			return 0

	def __eq__(self, other):
		return self.compr(other)==0

	def __ne__(self, other):
		return abs(self.compr(other))==1

	def __lt__(self, other):
		return self.compr(other)==-1

	def __gt__(self, other):
		return self.compr(other)==1

	def __le__(self, other):
		return self.compr(other)!=1

	def __ge__(self, other):
		return self.compr(other)!=-1
	
	def getHotPoints(s):
		return s.hotPoints

class ChessMatrix:
	"""
	"""
	def __init__(s, pX, pY):
		"""
		erzeuge aus den  X/Y-Dimensionen eine schachbrettartige Matrix (schwarze/weisse Felder)
		"""
#		print 'ChessMatrix: ',pX,pY
		s.xDim=pX
		s.yDim=pY
		field={'color':None, 'pic':None,'gap':0}
		col=[copy.deepcopy(field) for x in range(s.yDim)]
		s.matrix=[copy.deepcopy(col) for x in range(s.xDim)]
		s.listOfB=[]
		s.listOfW=[]
		#farbvergabe
		startColor='B'
		for i in range(len(s.matrix)):
			startColor='W' if startColor=='B' else 'B'
			currColor=startColor
			for j in range(len(col)):
				s.matrix[i][j]['color']=currColor
				# wir fuellen die lsten von schwazen und weissen feldern
				if currColor=='W':
					s.listOfW.append(s.matrix[i][j])
				else:
					s.listOfB.append(s.matrix[i][j])
				currColor='W' if currColor=='B' else 'B'
		random.shuffle(s.listOfB)
		random.shuffle(s.listOfW)
		s.listOf=s.listOfW+s.listOfB
		s.currPos=0
		
#		print 's.matrix: ', s.matrix

	def fill(s, pL):
		"""
		fuelle mit den uebergebenen elementen zufaellig eine farbe auf, ist sie fertig aufgefuellt
		setze mit der 2. farbe fort. wir beginnen standardmaessig mit farbe 'W'
		"""
		for p in pL:
			while s.listOf[s.currPos]['gap']==2:
				# es handelt sich um einen gap und der muss freigelassen werden
				s.currPos+=1
			# das bild taggen
			p.chessMatrixColor=s.listOf[s.currPos]['color']
			
			s.listOf[s.currPos]['pic']=p
			s.currPos+=1
		
	def fillGaps(s,pNum):
		"""
		fuelle luecken in matrix (dieser aufruf erfolgt zuerst)
		"""
# alte loesung:
#		s.fill([None]*pNum)
		if pNum>0:
			# aufbau einer liste mit allen positionen
			posL=[[x%s.xDim,x//s.xDim] for x in range(s.xDim*s.yDim)]
#		print 'posL: ', posL
			random.shuffle(posL)
			while len(posL)>0:
#				print 'len(posL): ',len(posL)
				mat=s.fillGapsRecursive(copy.deepcopy(s.matrix),pNum,posL.pop())
				if mat!=None:
#					print 'mat: ',mat
					for x in range(s.xDim):
						for y in range(s.yDim):
							s.matrix[x][y]['gap']=mat[x][y]['gap']
					break
#			print 'fillGaps() - End'

	def fillGapsRecursive(s,pMat,pNum,pPos):
		# wenn die uebergebene position oder die nachbarn 'gap'==True sind return False
#		print 'fgr: ',pNum,pPos
		if pMat[pPos[0]][pPos[1]]['gap']>0:
#			print 'fgr - None: 1',pMat[pPos[0]][pPos[1]]['gap']
			return None
		# matrix markieren
		for x in range(pPos[0]-1,pPos[0]+2):
			for y in range(pPos[1]-1,pPos[1]+2):
				if x>=0 and y>=0:
					try:
#						print 'X,Y: ',x,y
						pMat[x][y]['gap']=1
					except IndexError:
						pass
		try:
			pMat[pPos[0]][pPos[1]]['gap']=2
		except IndexError:
#			print 'fgr - None: 2'
			return None
		# keine weiteren gaps sind notwendig - wir sind am ziel
		if pNum<=1:

#			print 'fgr: 3'
			return pMat
		# zufaelligen roesselsprung veranstalten
		roesslSpr=[(1,2),(2,1),(-1,2),(-2,1),(1,-2),(2,-1),(-1,-2),(-2,-1)]
		random.shuffle(roesslSpr)
		retVal=None
		while len(roesslSpr)>0:
			currPos=copy.deepcopy(pPos)
			rs=roesslSpr.pop()
			currPos[0]+=rs[0]
			currPos[1]+=rs[1]
			if 0<=currPos[0] and currPos[0] <s.xDim and 0<=currPos[1] and currPos[1] <s.yDim :
				retVal=s.fillGapsRecursive(copy.deepcopy(pMat),pNum-1,currPos)
			if retVal!=None:
#				print 'fgr: 4'
				return retVal
#		print 'fgr - None: 5'
		return None
	
	def get(s):
		"""
		gib die matrix zurueck
		"""
		return s.matrix

class Coor(MyLogging):
	"""
	punkt Objekt mit der Information um welchen Eckpunkt es sich handelt
	"""
	def __init__(s, pX, pY, pCoorPos=None):
		s.checkCoorPos(pCoorPos)
		s.x=int(pX)
		s.y=int(pY)
		s.coorPos=pCoorPos
		s.coorReflectedD={'LU':'LU','RU':'LO','LO':'RU','RO':'RO'}
		s.coorRotatedD={'LU':'RO','RU':'LO','LO':'RU','RO':'LU'}

	def checkCoorPos(s,pCoorPos):
		if pCoorPos !=None and pCoorPos not in ('LO', 'LU', 'RO', 'RU'):
			raise AppError(pCoorPos,'No coordinate position!')

	def __repr__(s):
		return str((s.x,s.y,s.coorPos))

	def getCoor(s):
		return (s.x, s.y)

	def getCoorPos(s):
		return s.coorPos

	def setCoor(s, pX=None, pY=None):
		if pX!=None:
			s.x=int(pX)
		if pY!=None:
			s.y=int(pY)

	def setCoorPos(s,pCoorPos):
		s.checkCoorPos(pCoorPos)
		s.coorPos=pCoorPos

	def getRev(s):
		coor=Coor(s.y,s.x,s.coorPos)
		return coor

	def getReflected(s):
		"""
		Refelxion entlang der Diagonale von LU and RO
		"""
		coor=Coor(s.y,s.x,s.coorReflectedD[s.coorPos])
		return coor

	def getRotated(s):
		"""
		Um 180 Grad gedreht
		"""
		coor=Coor(gParGet('pageSize')[0]-s.x,gParGet('pageSize')[1]-s.y,s.coorRotatedD[s.coorPos])
		return coor


	def __add__(s,o):
		coor=Coor(s.x+o.x,s.y+o.y,s.coorPos)
		return coor

	def __sub__(s,o):
		coor=Coor(s.x-o.x,s.y-o.y,s.coorPos)
		return coor

	def getX(s):
		return s.x

	def getY(s):
		return s.y
		
	def distance(s,o):
		"""
		der abstand 2er punkte
		"""
		x_=abs(s.x-o.x)
		y_=abs(s.y-o.y)
		#return pow(pow(x_,2)+pow(y_,2),0.5)
		return ((x_**2)+(y_**2))**0.5

	def __eq__(s, o):
		if o==None:
#			print('__eq__(): False')
			return False
		if s.x==o.getX() and s.y==o.getY():
#			print('__eq__(): True')
			return True
		else:
#			print('__eq__(): False')
			return False

	def __ne__(s, o):
		if o==None:
#			print('__ne__(): True')
			return True
		if s.x==o.getX() and s.y==o.getY():
#			print('__ne__(): False')
			return False
		else:
#			print('__ne__(): True')
			return True

class Pic(MyLogging):
	"""
	Bildklasse
	Enthaelt alle Objekte und Methoden ueber ein Bildobjekt
	"""
	mmapfp=MyMap(-1,20000000)

	def __init__(s,pFile,pMinDiagonale):
		s.filename=pFile
		s.minDiagonale=pMinDiagonale
		s.dist=gParGet('optBorder')

		# parsen einiger exif/iptc-infos
		try:
			exiv=pyexiv2.Image(s.filename)
			s.picDate=datetime.datetime.strptime(exiv.read_exif()['Exif.Photo.DateTimeOriginal'],"%Y:%m:%d %H:%M:%S")
		except KeyError:
			try:
				s.picDate=datetime.datetime.strptime(exiv.read_xmp()['Xmp.exif.DateTimeOriginal'],"%Y-%m-%dT%H:%M")
			except KeyError:
				# optional koennte man das dateidatum verwenden
				s.picDate=None
		try:
			s.picCaption=exiv.read_iptc()['Iptc.Application2.Caption']
		except KeyError:
			s.picCaption=None

		# das bild wird mit der minimalgroesse initialisiert
		width, height=s.calcSize(s.minDiagonale)
		if s.picCaption!=None and gParGet('text')==True:
			# wenn's einen text gibt und dieser auch angedruckt werden soll
			s.innerBox=FooterBox(None,None,height,width,gParGet('picFooterHeight'))
		else:
			s.innerBox=Box(None,None,height,width)
		#s.innerBox=Box(None,None,height,width)
		s.outerBox=Box(None,None,height,width)
		#s.borders=[]	# liste der seiten, an welchen das bild an die seitenraender angedockt ist

		# text fuers debugging
		s.text=''

		s.outerBoxOverlapsL=[]

		# einige attribute die im vergroesserungsreigen (fitPics())von bedeutung sind ...
		# dictionary zum speichern der unmittelbaren nachbarn
		s.posStr='' #enthaelt informationen ueber die positionierung der innerBox in der outerBox dieses bildes
		#s.neighbours={} # dictionary mit schluesseln 'O','U','L','R' - was sind die nachbarn dieses bildes

		s.logdbg(inspect.currentframe())

	def setMinDiagonal(s,pDiagonal):
		s.minDiagonale=pDiagonal
		width, height=s.calcSize(s.minDiagonale)
		s.innerBox.set(None,None,height,width)
		s.outerBox.set(None,None,height,width)

	def setPosition(s,**p):
		"""
		durchrooten auf die box-funktion
		"""
		s.logdbg(inspect.currentframe())

		ret=s.innerBox.setPosition(**p)
		# wenn die outerBox noch leer ist, wird sie mit der innerBox initialisiert
		if s.outerBox.get()==None:
			s.outerBox.set(*s.innerBox.get())
		return ret

	def clearPosition(s):
		"""
		setze x/y auf None
		"""
		width, height=s.calcSize(s.minDiagonale)
		s.innerBox.clearPosition(width, height)
		s.outerBox.clearPosition(width, height)



	def setOuterBoxOverlaps(s, pL):
		"""
		zur uebergabe einer liste von bildern, deren outerBoxes mit
		der outerBox des aktuellen bildes ueberlappt
		"""
		s.outerBoxOverlapsL=pL

	def getOuterBoxOverlaps(s):
		"""
		rueckgabe der liste
		"""
		return s.outerBoxOverlapsL

	def x(s):
		return s.innerBox.x

	def y(s):
		return s.innerBox.getY()

	def set_x(s,px):
		s.innerBox.x=px

	def set_y(s,py):
		s.innerBox.y=py

	def w(s):
		return s.innerBox.w

	def h(s,pNetto=False):
		"""
		pNetto ... wegen FooterBox: mit diesem Parameter erhalten wir die Nettohoehe, i.e. die reine Bildhoehe
		"""
		if pNetto==False:
			return s.innerBox.getH()
		else:
			return s.innerBox.h

	def __repr__(s):
#		return str((s.filename,s.posStr,s.innerBox,s.outerBox))
		return str((s.filename,s.picDate))

	def getName(s):
		"""
		gibt den Filenamen zurueck
		"""
		s.logdbg(inspect.currentframe())

		return s.filename.split('/')[-1]

	def getDateTime(s):
		"""
		gibt den exif-timestamp zurueck
		"""
		return s.picDate

	def getCaption(s):
		"""
		gibt die IPTC-Caption zurueck
		"""
		return s.picCaption


	def getImage(s,pDPI):
		"""
		gibt das Bild in einer bestimmten groesse/aufloesung zurueck
		"""
		#print 1,(s.h,s.w)
		s.logdbg(inspect.currentframe())

		# zurueck an den start
		s.mmapfp.seek(0)
		# groessenanpassung des files und anschliessendes speichern als JPEG
#		s.getImageObj().resize((int(round(s.w()/inch*pDPI)),int(round(s.h()/inch*pDPI))),Image.ANTIALIAS).convert('RGB').save(s.mmapfp,'JPEG',quality=80,subsampling="4:4:4")
		s.getImageObj().resize((int(round(s.w()/inch*pDPI)),int(round(s.h()/inch*pDPI))),Image.ANTIALIAS).convert('RGB').save(s.mmapfp,'JPEG',quality=80,subsampling="4:4:4")
		# vermerken der filegroesse (wegen anonymen mmap)
		s.mmapfp.setSize()
		# zueuck an den start fuer's lesen
		s.mmapfp.seek(0)
		return Image.open(s.mmapfp)

	def	getImageObj(s):
		img=Image.open(s.filename)
		# das crop findet hier statt - ist aber fuer die performance wahrscheinlich nicht so gut ...
		if gParGet('crop')!=0:
			img=img.crop((gParGet('crop'), gParGet('crop'), img.size[0]-gParGet('crop'), img.size[1]-gParGet('crop')))
		return img

	def getOrientation(s):
		s.logdbg(inspect.currentframe())
		img=s.getImageObj()
		if img.size[0]<img.size[1]:
			return 'P'
		else:
			return 'L'

	def calcSize(s,pDiag):
		#vert=pow(pow(float(pDiag),2)/(1+pow(float(s.getImageObj().size[0])/float(s.getImageObj().size[1]),2)),0.5)
		img=s.getImageObj()
		vert=(((float(pDiag)**2)/(1+((float(img.size[0])/float(img.size[1]))**2)))**0.5)
		horz=vert*(float(img.size[0])/float(img.size[1]))
		return(int(round(horz,0)),int(round(vert,0)))

	def getMinSize(s, pFixHeight=None, pFixWidth=None):
		"""
		wird kein parameter uebergeben, geben wir die minimalgroesse, so wie von calcSize() uebergeben, zurueck.
		sind pFixHeight oder pFixWidth gegeben, passen wir die groesse an, wenn sie sich innerhalb eines
		thresholds befindet
		"""
		s.logdbg(inspect.currentframe())

		threshold=1*cm

		horz, vert=s.calcSize(s.minDiagonale)

		horzNeu, vertNeu=horz, vert
		if pFixHeight!=None:
			if abs(vert-pFixHeight)<threshold:
				vertNeu=pFixHeight
				horzNeu=int(round((float(horz)/float(vert))*vertNeu))
		elif pFixWidth!=None:
			if abs(horz-pFixWidth)<threshold:
				horzNeu=pFixWidth
				vertNeu=int(round((float(vert)/float(horz))*horzNeu))

		return(horzNeu, vertNeu)

	def getEdge(s,pLROU):
		return s.innerBox.getEdge(pLROU)

	def move(s,pHor=None,pVer=None):
		s.innerBox.move(pHor,pVer)

#	def setPos(s,pLinksUnten,pDimensionen=None,pKeepProportions=False):
#		s.innerBox.setPos(pLinksUnten,pDimensionen,pKeepProportions)
#		# wenn die outerBox noch leer ist, wird sie mit der innerBox initialisiert
#		if s.outerBox.get()==None:
#			s.outerBox.set(*s.innerBox.get())

	def initOuterBox(s,levelDict,borderL):
		# das erledigt das box-objekt fuer uns ...
		s.outerBox.setBoxFromLevels(levelDict)
		s.outerBox.setBorders(borderL)

	def positionInnerBox(s, pModus='', pLROU='',pOffset=0):
		"""
		die innerBox wird in der outerBox positioniert - abhaenig von der boderL der outerBox
		pModus: 'C'entered ... zentriert
		              'R'andom ... zufaellig
		              'O'pposite ... gegenueber
		              'D'efined ... ueber pLROU definiert
		              'B'iased ... bilder orientieren sich an der augenblicklichen position und werden um den betrag, den sie sich
		                               abseits des zentrums befinden auf der anderen seite angeordnet
		pOffset: ein mass um das die innerBox vom Rand entfernt plaziert wird - zusaetzlich zu s.dist - aber nur wenn genug platz ist
		"""
		hPos=''
		vPos=''
		posStr=''
		# horizontales positionieren der innerBox
		# abeitung aus s.outerBox.borderL
		if pModus not in ('O','B', 'C', 'R'): 
			# die strikte orientierung an den seitenraendern uebersteuern
			if (Side('L') in s.outerBox.borderL and not Side('R') in s.outerBox.borderL):
				hPos='L'
			elif (Side('R') in s.outerBox.borderL and not Side('L') in s.outerBox.borderL) :
				hPos='R'
		if hPos=='':
			if  (Side('R') in s.outerBox.borderL and Side('L') in s.outerBox.borderL) or pModus=='C':
				hPos='M'
			# zufaellig
			elif pModus=='R':
				hPos=random.choice(['L', 'R'])
			# gesteuert ueber pLROU
			elif pModus=='D' and ('L' in pLROU or 'R' in pLROU):
				hPos=[x for x in pLROU if x in ['L', 'R']][0]
			# nichts ist angegeben
			else:
				if s.outerBox.x+s.outerBox.w/float(2) >= s.innerBox.x+s.innerBox.w/float(2)  or  'L' in pLROU :
					hPos='R' if pModus=='O' else 'L'
				else:
					hPos='L' if pModus=='O' else 'R'

		cOffset=pOffset if s.outerBox.w-s.innerBox.w -2*s.dist>pOffset else 0
		if hPos=='L':
			s.innerBox.x=s.outerBox.x+s.dist + cOffset
			posStr+= 'L'
		elif hPos=='R':
			s.innerBox.x=s.outerBox.x+(s.outerBox.w-s.innerBox.w-s.dist - cOffset)
			posStr+= 'R'
		else:
			if pModus=='B':
				s.innerBox.x=s.outerBox.x*2+s.outerBox.w-s.innerBox.x-s.innerBox.w
			else:
				s.innerBox.x=s.outerBox.x+int(round((s.outerBox.w-s.innerBox.w)/float(2)))

		# vertikales positionieren der innerBox
		# abeitung aus s.outerBox.borderL
		if pModus not in ('O','B', 'C', 'R'): 
			# die strikte orientierung an den seitenraendern uebersteuern
			if (Side('U') in s.outerBox.borderL and not Side('O') in s.outerBox.borderL):
				vPos='U'
			elif (Side('O') in s.outerBox.borderL and not Side('U') in s.outerBox.borderL):
				vPos='O'
		if vPos=='':
			if  (Side('O') in s.outerBox.borderL and Side('U') in s.outerBox.borderL) or pModus=='C':
				vPos='M'
			# zufaellig
			elif pModus=='R':
				vPos=random.choice(['U', 'O'])
			# gesteuert ueber pLROU
			elif pModus=='D' and ('U' in pLROU or 'O' in pLROU):
				vPos=[x for x in pLROU if x in ['U', 'O']][0]
			# nichts ist angegeben
			else:
				if s.outerBox.y+(s.outerBox.h/float(2)) >= s.innerBox.y+(s.innerBox.h/float(2)):
					vPos='O' if pModus=='O' else 'U'
				else:
					vPos='U' if pModus=='O' else 'O'

		cOffset=pOffset if s.outerBox.h-s.innerBox.h -2*s.dist>pOffset else 0
		if vPos=='O':
			s.innerBox.y=s.outerBox.y+(s.outerBox.h-s.innerBox.h-s.dist -cOffset)
			posStr+= 'O'
		elif vPos=='U':
			s.innerBox.y=s.outerBox.y+s.dist+cOffset
			posStr+= 'U'
		else:
			if pModus=='B':
				s.innerBox.y=s.outerBox.y*2+s.outerBox.h-s.innerBox.y-s.innerBox.h
			else:
				s.innerBox.y=s.outerBox.y+int(round((s.outerBox.h-s.innerBox.h)/float(2)))
		if not s.checkPositioning():
			print ('positionsproblem positionInnerBox()!!!!!!!!!!', s.dist)

		s.posStr= posStr

#	def increaseSize(s,pHInc=None,pWInc=None,pModus=''):
	def increaseSize(s,pHInc=None,pWInc=None):
		"""
		die innerBox wird vergroessert, und zwar wird entweder die	hoehe oder die breite um den
		gegebenen betrag unter beibehaltung der proportionen erhoeht.
		dann wird getestet ob die innerBox noch groessenmaessig in die outerBox passt - wenn
		nein setzen wir die InnerBox zurueck und geben FALSE zurueck
		wir positionieren die innerBox unter beruecksichtigung der s.borders und gebenen
		abschliessend TRUE zurueck
			pHInc			...	horizontale vergroesserung
			pWInc			...	vertikale
			pCorner		... in dieser ecke wird das bild angeordnet
		"""
		s.logdbg(inspect.currentframe())

		# wir merken uns die orginalgroesse
		oldH=s.innerBox.h
		oldW=s.innerBox.w
		# vergroessern der innerBox
		s.innerBox.increaseSizeProportional(pHInc,pWInc)
		# check ob groesse noch passt
		if s.innerBox.h>s.outerBox.h-s.dist*2 or s.innerBox.w>s.outerBox.w-s.dist*2:
			#print 'increaseSize: FALSE'
			# die innerBox wird auf die orginalgroesse zurueckgesetzt
			s.innerBox.h=oldH
			s.innerBox.w=oldW
			return(False)
		else:
			#print 'increaseSize: TRUE'
#			s.positionInnerBox(pModus,pOffset=pHInc if pHInc<>None else pWInc)
			return(True)
		if not s.checkPositioning():
			print ('positionsproblem increaseSize()!!!!!!!!!!', s.dist)

	def maximizeSize(s,pCentered=True):
		"""
		die innerBox wird in der gegebenen outerBox maximiert - unter beruecksichtigung von pDist
		pCentered: defaultmaessig werden die bilder maximiert und dann in der outerBox zentriert.
		"""
		# berechnen der neuen groesse
		new_w=int(s.innerBox.w*(float(s.outerBox.h-(s.dist*2))/s.innerBox.h))
		new_h=int(s.innerBox.h*(float(s.outerBox.w-(s.dist*2))/s.innerBox.w))
		if s.outerBox.w-(s.dist*2)-new_w < s.outerBox.h-(s.dist*2)-new_h:
			s.innerBox.increaseSizeProportional(pHInc=new_h-s.innerBox.h)
		else:
			s.innerBox.increaseSizeProportional(pWInc=new_w-s.innerBox.w)
		# positionieren der box
		s.positionInnerBox( pModus='C' if pCentered else '')
		if not s.checkPositioning():
			print ('positionsproblem maximizeSize()!!!!!!!!!!', s.dist)

	def spazi(s):
		"""
		gibt's noch platz zur vergroesserung des bildes (abstand zur outerBox == dist*3) geben wir True zurueck
		"""
		if s.innerBox.h+(s.dist*3)<s.outerBox.h or s.innerBox.w+(s.dist*3)<s.outerBox.w:
			return True
		else:
			return False

	def checkPositioning(s):
		"""
		prueft, ob die innerBox korrekt in der outerBox positioniert ist.
		False: ein positionsproblem ist aufgetreten
		"""
		if s.innerBox.x-s.dist<s.outerBox.x or \
			s.innerBox.y-s.dist<s.outerBox.y or \
			s.innerBox.x+s.innerBox.w-s.dist>s.outerBox.x+s.outerBox.w or \
			s.innerBox.y+s.innerBox.h-s.dist>s.outerBox.y+s.outerBox.h:
			if s.innerBox.x-s.dist<s.outerBox.x:
				print ('checkPositioning(): L',s.outerBox.x,s.innerBox.x)
			elif s.innerBox.y-s.dist<s.outerBox.y:
				print ('checkPositioning(): U',s.outerBox.y,s.innerBox.y)
			elif s.innerBox.x+s.innerBox.w-s.dist>s.outerBox.x+s.outerBox.w:
				print ('checkPositioning(): R',s.outerBox.x+s.outerBox.w,s.innerBox.x+s.innerBox.w)
			elif s.innerBox.y+s.innerBox.h-s.dist>s.outerBox.y+s.outerBox.h:
				print ('checkPositioning(): O',s.outerBox.y+s.outerBox.h,s.innerBox.y+s.innerBox.h)
			return False
		else:
			return True

	def setOuterBox(s,pBox):
		"""
		hier wird die outerBox gesetzt - und die positionierung ueberprueft ...
		"""
		s.outerBox=pBox
#		if not s.checkPositioning():
#			# fehler!!!
#			raise AppError_(pBox,'OuterBox does not fit!: ')


	def addText(s, pT):
		s.text=s.text+pT

	def getText(s):
		return s.text

	def __hash__(s):
		return hash(s.filename)

	def __eq__(s, o):
		"""
		check auf gleichheit
		"""
		if s.filename==o.filename:
			return True
		else:
			return False

	def getArea(s):
		"""
		gibt die flaeche des Pics zurueck
		"""
		return s.innerBox.h*s.innerBox.w

	def findNeighbours(s,pLROU,pPicL,pOuterEdge=True):
		"""
		gibt eine (geordnete) liste der benachparten bilder zurueck
		pLROU ... L/R/O/U == gibt an, in welche richtung gesucht wird
		pOuterEdge ... verwende outer-edge logik true/false
		"""
		s.logdbg(inspect.currentframe())

		#print 'findNeighbours',pCurrPic,pLROU,pOuterEdge

		if pOuterEdge:
			myEdge=s.getOuterEdge(pLROU,pPicL)
		else:
			myEdge=s.getEdge(pLROU)

		#logging.info('N: '+str(pCurrPic))
		neighbourL=[]
		for p in pPicL:
			try:
				if p!=s:
					#print 'findNeighbours - loop',myEdge,p.getEdge(pLROU.opposite()),
					#logging.info('possible neighour: ' + str(myEdge) + ' - ' + str(p.getEdge(pLROU.opposite())))
					if (str(pLROU)=='L' or str(pLROU)=='U') and myEdge >= p.getEdge(pLROU.opposite()):
						#print 'TRUE'
						neighbourL.append(p)
					elif (str(pLROU)=='R' or str(pLROU)=='O') and myEdge <= p.getEdge(pLROU.opposite()):
						#print 'TRUE'
						neighbourL.append(p)
					#else:
					#	logging.info('no neighour: ' + str(p)+ str(myEdge) + ' - ' + str(p.getEdge(pLROU.opposite())))
#				print ("findNeighbours(): - Cmp - OK!!!!")
			except CmpError:
				#logging.info('CmpError')
#				print ("findNeighbours(): - CmpError")
				pass

		# sortieren der liste
		if str(pLROU)=='R' or str(pLROU)=='O':
			reve=False
		else:
			reve=True
		neighbourL.sort(key=lambda x: x.getEdge(pLROU.opposite()).level(),reverse=reve)
		#logging.info('neighbourL: '+str(pCurrPic)+'('+str(pLROU)+')'+' ## '+str(neighbourL))
		#print 'neighbourL',neighbourL
		return neighbourL

	def getOuterEdge(s,pLROU,pPicL):
		"""
		gibt die aeusseren kanten des aktuellen bildes zurueck
		pLROU ... L/R/O/U == gibt an, in welche richtung gesucht wird
		"""
		s.logdbg(inspect.currentframe())

		if str(pLROU) in 'OU':
			try:
				#print 'getOuterEdge',s.findNeighbours(pCurrPic,Side('L'),False)[0].getEdge(Side('L').opposite())
				#print 'getOuterEdge',s.findNeighbours(pCurrPic,Side('L'),False)[0].getEdge(Side('L').opposite()).level()
				x1=s.findNeighbours(Side('L'),pPicL,False)[0].getEdge(Side('L').opposite()).level()
			except IndexError:
				x1=s.x()
			try:
				#print 'getOuterEdge',s.findNeighbours(pCurrPic,Side('R'),False)[0].getEdge(Side('R').opposite())
				#print 'getOuterEdge',s.findNeighbours(pCurrPic,Side('R'),False)[0].getEdge(Side('R').opposite()).level()
				x2=s.findNeighbours(Side('R'),pPicL,False)[0].getEdge(Side('R').opposite()).level()
			except IndexError:
				x2=s.x()+s.w()
			if str(pLROU)=='O':
				y=s.y()+s.h()
			if str(pLROU)=='U':
				y=s.y()
			return (Edge(pLROU,(x1,y),(x2,y)))
		if str(pLROU) in 'RL':
			try:
				y1=s.findNeighbours(Side('U'),pPicL,False)[0].getEdge(Side('U').opposite()).level()
			except IndexError:
				y1=s.y()
			try:
				y2=s.findNeighbours(Side('O'),pPicL,False)[0].getEdge(Side('O').opposite()).level()
			except IndexError:
				y2=s.y()+s.h()
			if str(pLROU)=='R':
				x=s.x()+s.w()
			if str(pLROU)=='L':
				x=s.x()
			return(Edge(pLROU,(x,y1),(x,y2)))
		s.logerr('No Edge!')

class Box(MyLogging):
	"""
	Klasse enthält die Eckpunkte einer Box
	"""
	def __init__(s,*p):
		if isinstance(p[0],dict):
			if isinstance(p[0][list(p[0].keys())[0]],Line):
				s.setBoxFromLines(p[0])
			else:
				s.setBoxFromLevels(p[0])
		else:
#			if isinstance(p[0],Coor):
#				# setzen einer box ausgehend von einem punkt und einem abstand von diesem 'mittelpunkt'
#				s.setBoxFromLevels({'L':p[0].getX()-p[1],'R':p[0].getX()+p[1],'O':p[0].getY()+p[1],'U':p[0].getY()-p[1]})
#			else:
			s.set(*p)
		s.borderL=[]

	def set(s,x,y,height,width):
		s.x=int(x) if x!=None else None					# x position on the page
		s.y=int(y) if y!=None else None					# y position on the page
		s.h=int(height) if height!=None else None			# height on the page
		s.w=int(width)  if width!=None else None			# width on the page

	def setBoxFromLevels(s,levelDict):
		"""
		wir bekommen ein dictionary der form {<Side>:<level>,} und legen daraus die das box-objekt
		bestimmenden parameter x,y,h,w fest. wenn das dictionary nicht komplett ist, nehmen wir an, dass
		der rest unveraendert bleibt
		"""
		# bei bedarf verfollstaendigen wir das dictionary
		if not 'L' in levelDict:
			levelDict['L']=s.x
		if not 'R' in levelDict:
			levelDict['R']=s.x+s.w
		if not 'O' in levelDict:
			levelDict['O']=s.y+s.h
		if not 'U' in levelDict:
			levelDict['U']=s.y

		s.x=int(levelDict['L'])
		s.y=int(levelDict['U'])
		s.h=int(levelDict['O']-levelDict['U'])
		s.w=int(levelDict['R']-levelDict['L'])

	def setBoxFromLines(s, lineDict):
		"""
		wir bekommen ein dictionary der form {<Side>:<line>,} und legen daraus die das box-objekt
		bestimmenden parameter x,y,h,w fest
		"""
		levelDict={}
		levelDict['L']=lineDict['L'].level()
		levelDict['U']=lineDict['U'].level()
		levelDict['O']=lineDict['O'].level()
		levelDict['R']=lineDict['R'].level()
		s.setBoxFromLevels(levelDict)

	def getH(s):
		return s.h

	def getY(s):
		return s.y

	def setPosition(s,pCoorObj, pBorders =False, pSize=None, pProportional=True, pFix=False):
		"""
		parameter:
		* pCoorObj: ein Koordinatenobjekt
		    neu: fehlt die angabe des eckpunktes wird mittig positioniert
		* pBorders: sollen die Borders beruecksichtigt werden
		* pCurrBorder: hier kann man die Border mit einem aktuellen Wert ueberschreiben
		* pSize: neue (breite,hoehe) des pics. es muss/darf nur eines davon versorgt sein
		* pProportional: Groesse wird unter Beibehaltung der Proportionen angepasst
		* pFix: die groesse wird nur angepasst, wenn sie sich innerhalb des thresholds befindet
		was passiert:
		bild wird mit der aktuellen groesse unter berücksichtigung der borders angeordnet
		rueckgabe: dictionary der eckpunkte
		"""
		s.logdbg(inspect.currentframe())

		if pSize!=None:
			# groesse anpassen
			threshold=gParGet('fixSizeThreshold')
			if not pProportional:
				s.w, s.h=pSize
			else:
				if pSize[0]!=None:
					if not pFix or (abs(s.w-pSize[0])<threshold):
						#s.h=int(round(  (float(s.h)/s.w)*pSize[0] ))
						s.h=s.getNewSizeProportional(pW=pSize[0])
						s.w=pSize[0]
				else:
					if not pFix or (abs(s.h-pSize[1])<threshold):
						#s.w=int(round(  (float(s.w)/s.h)*pSize[1] ))
						s.w=s.getNewSizeProportional(pH=pSize[1])
						s.h=pSize[1]

		#positionieren
		if pBorders:
			b=gParGet('optBorder')
		else:
			b=0
		coorPos=pCoorObj.getCoorPos()
		coor=pCoorObj.getCoor()
		if coorPos=='LO':
			s.x, s.y=(coor[0]+b, coor[1]-s.h-b)
		elif coorPos=='LU':
			s.x, s.y=(coor[0]+b,coor[1]+b )
		elif coorPos=='RO':
			s.x, s.y=(coor[0]-s.w-b, coor[1]-s.h-b)
		elif coorPos== 'RU':
			s.x, s.y=(coor[0]-s.w-b, coor[1]+b)
		else: # keine angeabe des eckpunktes -> mittiges positionieren
			s.x, s.y=(coor[0]-int(round(s.w/2.0)), coor[1]-int(round(s.h/2.0)))

		return({'LU':Coor(s.x, s.y, 'LU')\
		        , 'LO':Coor(s.x, s.y+s.h, 'LO')\
		        , 'RO':Coor(s.x+s.w, s.y+s.h, 'RO')\
		        , 'RU':Coor(s.x+s.w, s.y, 'RU')})

	def clearPosition(s,pW,pH):
		"""
		unset current position
		"""
		s.x=None
		s.y=None
		s.w=int(pW)
		s.h=int(pH)

	def __repr__(s):
		try:
			l=s.w+s.x
			o=s.h+s.y
			return str((s.x,s.y,l,o,s.borderL))
		except TypeError:
			return str(None)

	def get(s):
		if s.x==None:
			# wir indizieren, dass das objekt leer ist
			return None
		return (s.x,s.y,s.getH(),s.w)

	def ul(s):
		"""
		oben links
		"""
		return (s.x,s.y+s.getH())

	def ur(s):
		"""
		oben rechts
		"""
		return (s.x+s.w,s.y+s.getH())

	def ll(s):
		"""
		unten links
		"""
		return (s.x,s.y)

	def lr(s):
		"""
		unten rechts
		"""
		return (s.x+s.w,s.y)

	def getNewSizeProportional(s,pH=None,pW=None):
		"""
		gibt die proportional richtige jeweils andere seite zurueck
		"""
		if pH!=None:
			y=pH
			Y=s.h
			X=s.w
		elif pW!=None:
			y=pW
			Y=s.w
			X=s.h
		x=int(round((float(X)/float(Y))*float(y)))
		return x


	def increaseSizeProportional(s,pHInc=None,pWInc=None):
		"""
		die Box wird vergroessert, und zwar wird entweder die	hoehe oder die breite um den
		gegebenen betrag unter beibehaltung der proportionen erhoeht.
		"""
		# berechne neues h und w
		if pHInc!=None:
			h=pHInc+s.h
			w=s.getNewSizeProportional(pH=h)
		elif pWInc!=None:
			w=pWInc+s.w
			h=s.getNewSizeProportional(pW=w)
		s.h=h
		s.w=w


	def move(s,pHor,pVer):
		"""
		verschieben einer box
		"""
		if pHor != None:
			s.x=s.x+pHor
		if pVer != None:
			s.y=s.y+pVer


	def getEdge(s,pLROU):
		"""
		gibt die kanten der aktuellen box zurueck
		pLROU ... L/R/O/U == gibt an, in welche richtung gesucht wird
		"""

		s.logdbg(inspect.currentframe())

		if str(pLROU)=='O':
			return (Edge(pLROU,(s.x,s.y+s.getH()),(s.x+s.w,s.y+s.getH())))
		if str(pLROU)=='U':
			return(Edge(pLROU,(s.x,s.y),(s.x+s.w,s.y)))
		if str(pLROU)=='R':
			return(Edge(pLROU,(s.x+s.w,s.y),(s.x+s.w,s.y+s.getH())))
		if str(pLROU)=='L':
			return(Edge(pLROU,(s.x,s.y),(s.x,s.y+s.getH())))
		logerr('No Edge!')

	def intersecting(s, o, pTouchOnly=True):
		"""
		gibt True zurueck, wenn die boxen sich ueberschneiden
		pTouchOnly ... es reicht, wenn sich die boxen nur beruehren
		"""
		# finde kreuzungspunkte
		h1=[s.getEdge(Side('O')),s.getEdge(Side('U'))]
		v1=[s.getEdge(Side('L')),s.getEdge(Side('R'))]

		h2=[o.getEdge(Side('O')),o.getEdge(Side('U'))]
		v2=[o.getEdge(Side('L')),o.getEdge(Side('R'))]

		xL=list(filter(lambda x:x!=None,[h1[0].getCrossPoint(v2[0]),h1[0].getCrossPoint(v2[1]),\
		                            h1[1].getCrossPoint(v2[0]),h1[1].getCrossPoint(v2[1]),\
		                            h2[0].getCrossPoint(v1[0]),h2[0].getCrossPoint(v1[1]),\
		                            h2[1].getCrossPoint(v1[0]),h2[1].getCrossPoint(v1[1])]))

		#print (list(xL))
		# fuege die 2*4 expunkte der boxen in die list ein
		xL=xL+[s.ul(),s.ll(),s.ur(),s.lr(),o.ul(),o.ll(),o.ur(),o.lr()]
		#print xL

		# aus dieser punkteliste muessen wir jene finden, die in beiden boxen enthalten sind
		xInterL=[]
		for x in xL:
			if s.checkPointContained(x) and o.checkPointContained(x) and x not in xInterL:
				xInterL.append(x)
		#print xInterL

		if xInterL==[]:
			return False
		else:
			if pTouchOnly:
				return True
			else:
				if len(xInterL)==4:
					# 4 eckpunkte bleiben ueber, d.h. wir haben es mit einer ganzen box zu tun -
					# also beruehren sich die boxen nicht nur, sonen ueberschneiden sich
					#print "Intersecting pTouchOnly=False",xInterL
					return True
				else:
					return False


	def setBorders(s,pBorderL):
		"""
		Hier setzen wir die BorderListe (enthaelt die seiten der box, welche an den
		seitenrand grenzen) auf boxlevel.
		"""
		s.borderL=pBorderL

	def getBoxLevelDict(s):
		"""
		gibt ein dictionary mit den leveln der box zurueck
		"""
		boxLevels={}
		boxLevels['L']=s.ul()[0]
		boxLevels['R']=s.ur()[0]
		boxLevels['O']=s.ul()[1]
		boxLevels['U']=s.ll()[1]
		return boxLevels

	def checkPointContained(s,pPoint):
		"""
		es wird ueberprueft, ob ein punkt in der box enthalten ist
		resultat: true, false
		"""
		if s.x<=pPoint[0] and pPoint[0]<=s.x+s.w and \
			 s.y<=pPoint[1] and pPoint[1]<=s.y+s.getH():
			return True
		else:
			return False

#	def setV(s, pLine):
#		"""
#		setzt y und h der box abhaengig von der uebergebenen vertikalen linie
#		"""
#		s.y=pLine.coor1[1]
#		s.h=pLine.coor2[1]-s.y

	def getOrientation(s):
		"""
		gibt die orientierung ((P)ortrait oder (L)andscape) der box zurueck
		"""
		if s.h<s.w:
			return 'P'
		else:
			return 'L'

#	def getArea(s):
#		"""
#		gibt die Flaecher der Box zurueck
#		"""
#		return s.h*s.w

	def contains(s,o):
		"""
		gibt True zurueck, wenn die uebergebene box vollstaendig in der aktuellen enthalten ist - sonst False
		"""
		if s.x<=o.x and s.y<=o.y and (s.x+s.w)>=(o.x+o.w) and (s.y+s.getH())>=(o.y+o.getH()):
			return True
		else:
			return False

	def getEnlargedBox(s,pIncrease):
		"""
		hier wird eine neue, um pIncrease vergroesserte Box zurueckgegeben
		"""
		return Box(s.x-pIncrease,s.y-pIncrease,s.getH()+2*pIncrease,s.w+2*pIncrease)

	def center(s):
		return Coor(s.x+s.w//2,s.y+s.h//2)

class FooterBox(Box):
	def __init__(s,*p):
		s.footerHeight=p[-1]
		Box.__init__(*p[:-1])

	def getH(s):
		return s.h+s.footerHeight

	def getY(s):
		return s.y+s.footerHeight

	def set(s,x,y,height,width):
		s.x=int(x)					# x position on the page
		s.y=int(y)					# y position on the page
		s.h=int(height-s.footerHeight)			# height on the page
		s.w=int(width)			# width on the page

	# REFACTORING !!!
	def setBoxFromLevels(s,levelDict):
		"""
		wir bekommen ein dictionary der form {<Side>:<level>,} und legen daraus die das box-objekt
		bestimmenden parameter x,y,h,w fest. wenn das dictionary nicht komplett ist, nehmen wir an, dass
		der rest unveraendert bleibt
		"""
		# bei bedarf verfollstaendigen wir das dictionary
		if not 'L' in levelDict:
			levelDict['L']=s.x
		if not 'R' in levelDict:
			levelDict['R']=s.x+s.w
		if not 'O' in levelDict:
			levelDict['O']=s.y+s.getH()
		if not 'U' in levelDict:
			levelDict['U']=s.y

		s.x=int(levelDict['L'])
		s.y=int(levelDict['U'])
		s.h=int(levelDict['O']-levelDict['U']-s.footerHeight)
		s.w=int(levelDict['R']-levelDict['L'])

	# REFACTORING !!!
	def setPosition(s,pCoorObj, pBorders =False, pSize=None, pProportional=True, pFix=False):
		"""
		parameter:
		* pCoorObj: ein Koordinatenobjekt
		* pBorders: sollen die Borders beruecksichtigt werden
		* pCurrBorder: hier kann man die Border mit einem aktuellen Wert ueberschreiben
		* pSize: neue (breite,hoehe) des pics. es muss/darf nur eines davon versorgt sein
		* pProportional: Groesse wird unter Beibehaltung der Proportionen angepasst
		* pFix: die groesse wird nur angepasst, wenn sie sich innerhalb des thresholds befindet
		was passiert:
		bild wird mit der aktuelen groesse unter berücksichtigung der borders angeordnet
		rueckgabe: dictionary der eckpunkte
		"""
		s.logdbg(inspect.currentframe())

		if pSize!=None:
			# groesse anpassen
			threshold=gParGet('fixSizeThreshold')
			if not pProportional:
				s.w, h=pSize
				s.h=h-s.footerHeight
			else:
				if pSize[0]!=None:
					if not pFix or (abs(s.w-pSize[0])<threshold):
						#s.h=int(round(  (float(s.h)/s.w)*pSize[0] ))
						s.h=s.getNewSizeProportional(pW=pSize[0])
						s.w=pSize[0]
				else:
					if not pFix or (abs(s.h-pSize[1])<threshold):
						#s.w=int(round(  (float(s.w)/s.h)*pSize[1] ))
						s.w=s.getNewSizeProportional(pH=pSize[1]-s.footerHeight)
						s.h=pSize[1]-s.footerHeight

		#positionieren
		if pBorders:
			b=gParGet('optBorder')
		else:
			b=0
		coorPos=pCoorObj.getCoorPos()
		coor=pCoorObj.getCoor()
		if coorPos=='LO':
			s.x, s.y=(coor[0]+b, coor[1]-s.h-b)
		elif coorPos=='LU':
			s.x, s.y=(coor[0]+b,coor[1]+b )
		elif coorPos=='RO':
			s.x, s.y=(coor[0]-s.w-b, coor[1]-s.h-b)
		else: # 'RU'
			s.x, s.y=(coor[0]-s.w-b, coor[1]+b)

		return({'LU':Coor(s.x, s.y, 'LU')\
		        , 'LO':Coor(s.x, s.y+s.h, 'LO')\
				, 'RO':Coor(s.x+s.w, s.y+s.h, 'RO')\
				, 'RU':Coor(s.x+s.w, s.y, 'RU')})

class BoxStore(MyLogging):
	"""
	Klasse fuers Handling von Kandidatenlisten (und mehr?)
	"""
	def __init__(s):
		s.bL=[]

	def add(s,pBox):
		"""
		eine box wird zum store dazugefuegt, gleichzeitig werden boxen, welche in der uebergebenen vollstaendig enthalten sind
		aus dem store geloescht
		sollte die uebergebene box in einer box im store vollstaendig enthalten sein, wird sie nicht dazugefuegt
		"""
		contained=False
		for i,b in enumerate(s.bL):
			if b.contains(pBox):
				# die uebergebene box ist vollstaendig enthalten - wir machen nix
				contained=True
				break
			if pBox.contains(b):
				s.bL.remove(s.bL[i])
		if not contained:
			s.bL.append(pBox)

	def get(s):
		return s.bL


class HotPointCollection(MyLogging):
	"""
	Klasse verwaltet die Sammlung von heissen Punkten einer Seite
	"""

	def __init__(s,pDirection):
		"""
		pDirection ... hier wird angegeben in welche richtung gearbeitet wird. zur Auswah steht RU-LU, LO-LU, LO-RO und RU-RO
		"""
		s.logdbg(inspect.currentframe())

		s.pointL=[]		# nicht-geordnete knotenliste
		# ein knoten besteht aus x-koordinate, y-koordinate und einem
		# indikator, der angibt, aus welcher ecke des quellbildes
		# der knoten stammt
		if pDirection not in ('RU-LU', 'LO-LU', 'LO-RO', 'RU-RO'):
			raise AppError(pDirection,'No supported direction!')
		s.direction=pDirection

	def transform(s,pCoor):
		if s.direction=='RU-LU':
			return pCoor
		elif s.direction=='LO-LU':
			return pCoor.getReflected()
		elif s.direction=='LO-RO':
			return pCoor.getRotated()
		else: # 'RU-RO'
			return pCoor.getReflected().getRotated()

	def addPoint(s,pCoor):
		"""
		punkt dazufuegen und gegebenfalls obsolete knoten loeschen
		"""
		s.logdbg(inspect.currentframe())

		lCoor=s.transform(pCoor)
		s.loginfo(str(( 'add',5,lCoor)))

		# loesche rechten untern quadranten
		cnt=0
		try:
			while 1:
				#print 'pCoor',pCoor
				print ('lCoor',lCoor)
				print ('s.pointL[cnt]',s.pointL[cnt])
				if s.pointL[cnt].getCoor()[0]>=lCoor.getCoor()[0] and ((s.pointL[cnt].getCoor()[1]<lCoor.getCoor()[1] and lCoor.getCoorPos()=='RO') or \
					(s.pointL[cnt].getCoor()[1]<=lCoor.getCoor()[1] and lCoor.getCoorPos()=='LU')):
					# hier werden die vom einzufuegenden knoten aus im rechten unteren quadranten liegenden knoten geloescht.
					# wobei abhaengig von ROoder LU unterschiedlich vorgegangen wird:
					# 'RO' ... es bleiben die knoten auf gleicher hoehe erhalten
					# 'LU' ... es werden auch die knoten auf gleicher hoehe entfernt
					if s.pointL[cnt].getCoorPos()=='RO' and lCoor.getCoorPos()=='LU':
						# hier verschieben wir den aktuellen knoten auf die hoehe des zu loeschenden
						# knotens, wenn es ein RO ist
						lCoor.setCoor(pY=s.pointL[cnt].getCoor()[1])
					if s.pointL[cnt].getCoorPos()=='LU' and lCoor.getCoorPos()=='LU' and s.pointL[cnt].getCoor()[1]<lCoor.getCoor()[1]:
						# wenn der einzufuegende knoten ein 'LU' ist, und sich ein 'LU'-knoten in der liste befindet, der ich unterhalb des einzufuegenden
						# befindet, wird dieser nicht geloescht, sondern nach links auf die hoehe des einzufuegenden verschoben
						s.pointL[cnt].setCoor(lCoor.getCoor()[0],s.pointL[cnt].getCoor()[1])
						cnt=cnt+1
					elif s.pointL[cnt].getCoorPos()=='RO' and lCoor.getCoorPos()=='RO' and s.pointL[cnt].getCoor()[1]<lCoor.getCoor()[1]:
						# wenn der einzufuegende knoten ein 'RO' ist, und sich ein 'RO'-knoten in der liste befindet, der ich unterhalb des einzufuegenden
						# befindet, wird dieser nicht geloescht, sondern auf die hoehe des einzufuegenden verschoben
						s.pointL[cnt].setCoor(s.pointL[cnt].getCoor()[0],lCoor.getCoor()[1])
						cnt=cnt+1
					else:
						s.pointL.pop(cnt)
				else:
					cnt=cnt+1
		except IndexError:
			pass
		# fuege aktuellen knoten in die sortierte liste ein
		s.pointL.append(lCoor)

		s.loginfo(str(( 'add',3,s.pointL)))

	def sortPointL(s,x):
		"""
		sort-funktion fuer pointL in getNext
		"""
		if x.getCoorPos()=='LU':
			# 'LU'-punkte sollen vertikal aufsteigend sortiert werden
			return (x.getCoorPos(),x.getCoor()[1])
		else:
			# 'RO'-punkte sollen horizontal absteigend sortiert werden
			return (x.getCoorPos(),-x.getCoor()[0])

	def getNext(s,pCoor,pCount=1):
		"""
		von rechts unten nach links oben aufsteigend
		pCount gibt an, den wievielten knoten wir wollen
		"""
		s.logdbg(inspect.currentframe())

		lCoor=s.transform(pCoor)
		cnt=pCount
		#logging.info(str(( 'get',7,pCoor,pCount,sorted(s.pointL,key=lambda x: (x[2],-x[0])))))
		#print str(( 'get',7,pCoor,pCount,sorted(s.pointL,key=lambda x: (x[2],-x[0]))))
		for c in sorted(s.pointL,key=s.sortPointL):
			if c.getCoor()[0]<=lCoor.getCoor()[0] or c.getCoor()[1]>=lCoor.getCoor()[1]:
				cnt=cnt-1
				if cnt==0:
					s.loginfo(str(( 'get',4,c)))
					return s.transform(c)
		# wenn wir nix passendes gefunden haben
		s.loginfo(str(('get',4.1,None)))
		return None

	def getList(s):
		"""
		fuer's debuggen ...
		"""
		return s.pointL

class Side(MyLogging):
	"""
	datentyp fuer seiten
	"""
	def __init__(s,pSide):
		s.currSide=''
		s.logdbg(inspect.currentframe())

		s.sideL=['O','U','L','R']
		if pSide in s.sideL:
			s.currSide=pSide
		else:
			#print 'side',pSide
			raise AppError(pSide,'Side does not exist: ')

	def __repr__(s):
		return s.currSide

	def opposite(s):
		s.logdbg(inspect.currentframe())

		if s.currSide=='L':
			return Side('R')
		if s.currSide=='R':
			return Side('L')
		if s.currSide=='O':
			return Side('U')
		if s.currSide=='U':
			return Side('O')

	def direction(s):
		"""
		horizontal/vertikal
		"""
		s.logdbg(inspect.currentframe())

		if s.currSide in ['O','U']:
			return 'H'
		else:
			return 'V'

	def __eq__(s,o):
		"""
		test auf gleichheit
		"""
		if s.currSide==o.currSide:
			return True
		else:
			return False

class Line(MyLogging):
	"""
	Linienobjekt
	"""
	def __init__(s,pCoor1,pCoor2):
		# check, ob es sich um eine horzontale/vertikale handelt
		# und sortieren der koordinaten
		if pCoor1==pCoor2:
			s.direction=None
		if pCoor1[0]==pCoor2[0]:
			s.direction='V'
		elif pCoor1[1]==pCoor2[1]:
			s.direction='H'
		else:
			raise AppError((pCoor1,pCoor2),'Line is neither horizontal nor vertical: ')

		if s.direction=='H':
			if pCoor1[0]<pCoor2[0]:
				s.coor1=pCoor1
				s.coor2=pCoor2
			else:
				s.coor1=pCoor2
				s.coor2=pCoor1
		else:
			if pCoor1[1]<pCoor2[1]:
				s.coor1=pCoor1
				s.coor2=pCoor2
			else:
				s.coor1=pCoor2
				s.coor2=pCoor1

	def __repr__(s):
		# kein logging bei __repr__()
		return str((s.coor1,s.coor2))

	def getCrossPoint(s,o):
		"""
		gibt einen kreuzungspunkt zweier kanten zurueck. wenn dieser nicht vorhanden ist,
		dann None
		"""
		#print 'getCrossPoint',s,o
		x=None
		y=None
		if s._sideIndMatches_(s.side,o.side):
			#return NotImplemented
			raise CmpError
		if s.side.direction() =='H':
			x1=s.coor1[0]
			x2=o.coor1[0]
			x3=s.coor2[0]
			y1=o.coor1[1]
			y2=s.coor1[1]
			y3=o.coor2[1]
		else:	# 'H'
			x1=o.coor1[0]
			x2=s.coor1[0]
			x3=o.coor2[0]
			y1=s.coor1[1]
			y2=o.coor1[1]
			y3=s.coor2[1]

		if x1<=x2 and x2<=x3:
			x=x2
		if y1<=y2 and y2<=y3:
			y=y2

		if x==None or y==None:
			return None
		else:
			#print (x,y)
			return (x,y)

	def overlap(s,o):
		"""
		wenn sich 2 linien gleicher ausrichtung ueberlappen geben wir True zurueck, sonst false
		"""
		if s.direction =='V':
			if s.coor1[1]>o.coor2[1] or s.coor2[1]<o.coor1[1]:
				# kanten ueberdecken sich nicht
#				print("Overlap:False!")
				return False
			else:
#				print("Overlap:True!")
				return True
		else:
			if s.coor1[0]>o.coor2[0] or s.coor2[0]<o.coor1[0]:
				# kanten ueberdecken sich nicht
#				print("Overlap:False!")
				return False
			else:
#				print("Overlap:True!")
				return True

	def __le__(s,o):
		"""
		kleinergleich
		die seiten muessen den gleichen seitenindikator haben oder opposite sein und sie
		muessen sich teilweise ueberdecken. der vergleich bezieht sich auf die position
		auf dem canvas
		"""
		s.logdbg(inspect.currentframe())

		#print '__le__',s,o

		if not s._sideIndMatches_(s.side,o.side):
			#return NotImplemented
			raise CmpError
		if s.overlap(o):
			if s.direction =='V':
				if s.coor1[0]<=o.coor1[0]:
					#print '__le__ True'
					return True
				else:
					#print '__le__ False'
					return False
			else: # 'H'
				if s.coor1[1]<=o.coor1[1]:
					#print '__le__ True'
					return True
				else:
					#print '__le__ False'
					return False
		else:
			# keine ueberlappung
				raise CmpError

	def __ge__(s,o):
		"""
		groessergleich
		die seiten muessen den gleichen seitenindikator haben oder opposite sein und sie
		muessen sich teilweise ueberdecken. der vergleich bezieht sich auf die position
		auf dem canvas
		"""
		s.logdbg(inspect.currentframe())

		#print '__ge__',s,o

		if not s._sideIndMatches_(s.side,o.side):
			#return NotImplemented
			raise CmpError
		if s.overlap(o):
			if s.direction =='V':
				if s.coor1[0]>=o.coor1[0]:
					#print '__ge__ True'
					return True
				else:
					#print '__ge__ False'
					return False
			else: # 'H'
				if s.coor1[1]>=o.coor1[1]:
					#print '__ge__ True'
					return True
				else:
					#print '__ge__ False'
					return False
		else:
			# keine ueberlappung
				raise CmpError

	def __eq__(s, o):
		"""
		check auf gleichheit
		"""
		if s.coor1==o.coor1 and s.coor2==o.coor2:
			return True
		else:
			return False


	def _sideIndMatches_(s,side1,side2):
		"""
		ueberprueft, ob die beiden seiten die gleiche ausrichtung haben
		"""
		s.logdbg(inspect.currentframe())

		if (side1.direction()=='V' and side2.direction()=='V') or (side1.direction()=='H' and side2.direction()=='H'):
			return True
		else:
			return False

	def level(s):
		"""
		gibt die 'hoehe' der linie zurueck - ermoeglicht sortieren
		ohne beachtung der ueberdeckung
		"""
		if s.direction=='V':
			return s.coor1[0]
		else:
			return s.coor1[1]

	def length(s):
		"""
		gibt die laenge der linie zurueck
		"""
		if s.direction=='V':
			return abs(s.coor1[1]-s.coor2[1])
		else:
			return abs(s.coor1[0]-s.coor1[0])

	def __sub__(s, o):
		"""
		subtrahiere s -o
		"""
		if not s._sideIndMatches_(s.side,o.side):
			raise AppError
		if not s.level()==o.level():
			raise AppError
		if s.direction=='V':
			if s.coor1[1]<=o.coor1[1] and o.coor1[1]<=s.coor2[1]:
				return Line(s.coor1, o.coor1)
			elif s.coor1[1]<=o.coor2[1] and o.coor2[1]<=s.coor2[1]:
				return Line(o.coor2, s.coor2)
			else:
				return None
		else:
			if s.coor1[0]<=o.coor1[0] and o.coor1[0]<=s.coor2[0]:
				return Line(s.coor1, o.coor1)
			elif s.coor1[0]<=o.coor2[0] and o.coor2[0]<=s.coor2[0]:
				return Line(o.coor2, s.coor2)
			else:
				return None


class Edge(Line, MyLogging):
	"""
	kantenobjekt
	enthält vergleichsmethoden
	"""
	def __init__(s,pSide,pCoor1,pCoor2):
		s.side=pSide
		#s.direction=s.side.direction()

		# initialisieren des Subobjektes
		Line.__init__(s,pCoor1,pCoor2)

		# check, ob die gegebene ausrichtung mit der festgestellten uebereinstimmt
		#print 1,s.direction,s.side,s.side.direction()
		if s.direction != None and pCoor1!=pCoor2 and s.direction!= s.side.direction():
			if s.direction=='V':
				print (s.direction,s.side.direction())
				raise AppError(str(pCoor1)+"|"+str(pCoor2),'No vertical line!')
			else:
				print (s.direction,s.side.direction())
				raise AppError(str(pCoor1)+"|"+str(pCoor2),'No horizontal line!')

		s.logdbg(inspect.currentframe())

	def __repr__(s):
		# kein logging bei __repr__()
		return str([s.side,s.direction,(s.coor1,s.coor2)])

class LinesOnALevel(MyLogging):
	"""
	jedes obekt ist augezeichnet durch eine Ausrichtung (H/V) durch ein level und 1..n Line-Objekte
	"""
	def __init__(s, pLineObj):
		s.direction=pLineObj.direction
		s.level=pLineObj.level()
		s.lineL=[pLineObj]

	def __repr__(s):
		return str([s.direction, s.level,s.lineL])

	def add(s, pLineObj):
		if s.direction!=pLineObj.direction or s.level!=pLineObj.level():
			raise AppError(pLineObj,'Line does not fit: ')
		elif pLineObj not in s.lineL:
			s.lineL.append(pLineObj)

	def getLineL(s):
		return s.lineL

	def getLevel(s):
		return s.level

	def overlap(s, pLine):
		"""
		checkt ob irgendeine Linie des aktuellen Objektes sich mit der gegebenen Linie
		ueberdeckt
		"""
		for l in s.lineL:
			if l.overlap(pLine):
				return True
		return False

class LinesOnLevelStore(MyLogging):
	"""
	verwaltet LinesOnALevel-Objekte gleicher Ausrichtung
	"""
	def __init__(s):
		s.direction=None
		s.lolD={}

	def __repr__(s):
		return str(s.lolD)

	def add(s, pLineObj):
		if s.direction==None:
			s.direction=pLineObj.direction
		elif s.direction!=pLineObj.direction:
			print (str(s.direction)+" "+str(pLineObj.direction))
			raise AppError(pLineObj,'Line does not fit: ')
		try:
			s.lolD[pLineObj.level()].add(pLineObj)
		except KeyError:
			s.lolD[pLineObj.level()]=LinesOnALevel(pLineObj)

#	def iterMe(s, reverse):
#		l=list(s.lolD)
#		l.sort(reverse=reverse)
#		for r in l:
#			yield s.lolD[r]

	def getNth(s,pInd, reve):
# TO BE REFCTORED !! #######################################################################
		"""
		gebe das n-te element geordnet nach reverse zurueck
		"""
		l=list(s.lolD)
#		print ("getNth(s,pInd, reve)--->")
#		print (l,len(l),pInd)
#		print ("<---getNth(s,pInd, reve)")
		l.sort(reverse=reve)
		return(s.lolD[l[pInd]])

	def len(s):
		"""
		gebe die anzahl der dictionary-elemente zurueck
		"""
		return len(s.lolD)
