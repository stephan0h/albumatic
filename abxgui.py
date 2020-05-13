# copyright Stephan Herschel - 2009-2011

import wx
from reportlab.lib.units import cm
import albumatix

class ABXFrame(wx.Dialog):
	def __init__(s, parent, id, title):
		s.winSize=(400,400)
		
		wx.Dialog.__init__(s, parent, id, title, size=(500, 500))
		
		box1=wx.BoxSizer(wx.VERTICAL)

		s.parPoster=wx.CheckBox(s, -1 ,'Poster')
		box1.Add(s.parPoster)
		s.parExif=wx.CheckBox(s, -1 ,'Exif')
		box1.Add(s.parExif)
		s.parDouble=wx.CheckBox(s, -1 ,'Double Pages')
		box1.Add(s.parDouble)
		s.parText=wx.CheckBox(s, -1 ,'Text')
		box1.Add(s.parText)
		
		boxH1=wx.BoxSizer(wx.HORIZONTAL)
		s.parDPI= wx.TextCtrl(s, -1, '50' )
		boxH1.Add(wx.StaticText(s, -1, 'DPI of Poster:'),1,wx.ALL,2)
		boxH1.Add(s.parDPI,0,wx.ALL,2)
		box1.Add(boxH1)
		
		boxH2=wx.BoxSizer(wx.HORIZONTAL)
		s.parBorder = wx.TextCtrl(s, -1, '0.5')
		boxH2.Add(wx.StaticText(s, -1, 'Distance between Pictures:'),1,wx.ALL,2)
		boxH2.Add(s.parBorder,0,wx.ALL,2)
		box1.Add(boxH2)
		
		boxH3=wx.BoxSizer(wx.HORIZONTAL)
		s.parNumOfPages = wx.TextCtrl(s, -1, '')
		boxH3.Add(wx.StaticText(s, -1, 'Number of Pages:'),1,wx.ALL,2)
		boxH3.Add(s.parNumOfPages,0,wx.ALL,2)
		box1.Add(boxH3)
		
		boxH4=wx.BoxSizer(wx.HORIZONTAL)
		boxH4.Add(wx.StaticText(s, -1, 'Page Size(cm): '),1,wx.ALL,2)
		boxH4.Add(wx.StaticText(s, -1, 'X-'),0,wx.ALL,2)
		s.parPageSizeX = wx.TextCtrl(s, -1, '20')
		boxH4.Add(s.parPageSizeX,0,wx.ALL,2)
		boxH4.Add(wx.StaticText(s, -1, 'Y-'),0,wx.ALL,2)
		s.parPageSizeY = wx.TextCtrl(s, -1, '20')
		boxH4.Add(s.parPageSizeY,0,wx.ALL,2)
		box1.Add(boxH4)
		
		boxH5=wx.BoxSizer(wx.HORIZONTAL)
		s.parWindowSize = wx.TextCtrl(s, -1, '30')
		boxH5.Add(wx.StaticText(s, -1, 'Window Size:'),1,wx.ALL,2)
		boxH5.Add(s.parWindowSize,0,wx.ALL,2)
		box1.Add(boxH5)
		
		boxH6=wx.BoxSizer(wx.HORIZONTAL)
		boxH6.Add(wx.StaticText(s, -1, 'Page Margins: '),1,wx.ALL,2)
		boxH6.Add(wx.StaticText(s, -1, 'O-'),0,wx.ALL,2)
		s.parPageDistO = wx.TextCtrl(s, -1, '1')
		boxH6.Add(s.parPageDistO,0,wx.ALL,2)
		boxH6.Add(wx.StaticText(s, -1, 'U-'),0,wx.ALL,2)
		s.parPageDistU = wx.TextCtrl(s, -1, '1')
		boxH6.Add(s.parPageDistU,0,wx.ALL,2)
		boxH6.Add(wx.StaticText(s, -1, 'L-'),0,wx.ALL,2)
		s.parPageDistL = wx.TextCtrl(s, -1, '1')
		boxH6.Add(s.parPageDistL,0,wx.ALL,2)
		boxH6.Add(wx.StaticText(s, -1, 'R-'),0,wx.ALL,2)
		s.parPageDistR = wx.TextCtrl(s, -1, '1')
		boxH6.Add(s.parPageDistR,0,wx.ALL,2)
		box1.Add(boxH6)
		
		boxH7=wx.BoxSizer(wx.HORIZONTAL)
		boxH7.Add(wx.StaticText(s, -1, 'Number of Pages for each seperate PDF-File:'),1,wx.ALL,2)
		s.parMaxPDFlen = wx.TextCtrl(s, -1, '')
		boxH7.Add(s.parMaxPDFlen,0,wx.ALL,2)
		box1.Add(boxH7)
		
		boxH8=wx.BoxSizer(wx.HORIZONTAL)
		boxH8.Add(wx.StaticText(s, -1, 'Background Colour [0..1]:'),1,wx.ALL,2)
		boxH8.Add(wx.StaticText(s, -1, 'R-'),0,wx.ALL,2)
		s.parBackColourR = wx.TextCtrl(s, -1, '0')
		boxH8.Add(s.parBackColourR,0,wx.ALL,2)
		boxH8.Add(wx.StaticText(s, -1, 'G-'),0,wx.ALL,2)
		s.parBackColourG = wx.TextCtrl(s, -1, '0')
		boxH8.Add(s.parBackColourG,0,wx.ALL,2)
		boxH8.Add(wx.StaticText(s, -1, 'B-'),0,wx.ALL,2)
		s.parBackColourB = wx.TextCtrl(s, -1, '0')
		boxH8.Add(s.parBackColourB,0,wx.ALL,2)
		box1.Add(boxH8)
		
		boxH9=wx.BoxSizer(wx.HORIZONTAL)
		boxH9.Add(wx.StaticText(s, -1, 'Number of Pictures'),1,wx.ALL,2)
		s.parNumPics = wx.TextCtrl(s, -1, '')
		boxH9.Add(s.parNumPics,0,wx.ALL,2)
		box1.Add(boxH9)
		
		boxH10=wx.BoxSizer(wx.HORIZONTAL)
		boxH10.Add(wx.StaticText(s, -1, 'Album/Poster Name'),1,wx.ALL,2)
		s.parName = wx.TextCtrl(s, -1, 'test')
		boxH10.Add(s.parName,0,wx.ALL,2)
		box1.Add(boxH10)
		
		boxH11=wx.BoxSizer(wx.HORIZONTAL)
		boxH11.Add(wx.StaticText(s, -1, 'Picture Location: '),1,wx.ALL,2)
		s.parPicLoc = wx.TextCtrl(s, -1, '',size=(300,25))
		boxH11.Add(s.parPicLoc,0,wx.ALL,2)
		box1.Add(boxH11)
		
		boxH12=wx.BoxSizer(wx.HORIZONTAL)
		boxH12.Add(wx.StaticText(s, -1, 'Initial Picture Size:'),1,wx.ALL,2)
		s.parInitPicSize = wx.TextCtrl(s, -1, '')
		boxH12.Add(s.parInitPicSize,0,wx.ALL,2)
		box1.Add(boxH12)
		
		box1.Add(wx.Button(s, 1, 'Ok'))
		
		s.Bind(wx.EVT_BUTTON, s.OnClose, id=1)
		s.SetSizer(box1)
		s.Centre()
		s.ShowModal()
		s.Destroy()
	
	def OnClose(s, event):
#		print dir (s.parPoster)
		print 'parPoster: ',s.parPoster.Value
		print 'parExif: ',s.parExif.Value
		print 'parDouble: ',s.parDouble.Value
		print 'parText: ',s.parText.Value
		print 'parDPI: ',s.parDPI.Value
		print 'parBorder: ',s.parBorder.Value
		print 'parNumOfPages: ',s.parNumOfPages.Value
		print 'parPageSize: ',s.parPageSizeX.Value,'-',s.parPageSizeY.Value
		print 'parWindowSize: ',s.parWindowSize.Value
		print 'parPageDist: ',s.parPageDistO.Value,'-',s.parPageDistU.Value,'-',s.parPageDistL.Value,'-',s.parPageDistR.Value
		print 'parMaxPDFlen: ',s.parMaxPDFlen.Value
		print 'parBackColour: ',s.parBackColourR.Value,'-',s.parBackColourG.Value,'-',s.parBackColourB.Value
		print 'parNumPics: ',s.parNumPics .Value
		print 'parName: ',s.parName.Value
		print 'parPicLoc: ',s.parPicLoc.Value
		print 'parInitPicSize: ',s.parInitPicSize.Value
		s.Close()
		s.createAlb()


	def createAlb(s):
			# setzen der parameter und aufruf von albumatix
			mObj=albumatix.Main() # setzen der defaultparameter

			# rgb
			albumatix.gParSet('poster',s.parPoster.Value)
			try:
				albumatix.gParSet('pageSize',(float(s.parPageSizeX.Value)*cm,float(s.parPageSizeY.Value)*cm))
			except ValueError:
				pass
			try:
				albumatix.gParSet('backgroundColour',(float(s.parBackColourR.Value),float(s.parBackColourG.Value),float(s.parBackColourB.Value)))
			except ValueError:
				pass
			try:
				albumatix.gParSet('optDpi',int(s.parDPI.Value))
			except ValueError:
				pass
			try:
				albumatix.gParSet('optBorder',float(s.parBorder.Value)*cm)
			except ValueError:
				pass
			albumatix.gParSet('optUseExif',s.parExif.Value)
			try:
				albumatix.gParSet('pageDist',{'O':int(round(float(s.parPageDistO.Value)*cm)), 'U':int(round(float(s.parPageDistO.Value)*cm)), 'L':int(round(float(s.parPageDistO.Value)*cm)), 'R':int(round(float(s.parPageDistO.Value)*cm))})
			except ValueError:
				pass
			albumatix.gParSet('text',s.parText.Value)

			albumatix.gParSet('albumname',s.parName.Value+'.pdf')
			albumatix.gParSet('albumgloblist',[(s.parPicLoc.Value+'/*.[jJ][pP][gG]',float(s.parInitPicSize.Value))])
			
			albumatix.gParSet('doublePage',s.parDouble.Value)
			try:
				albumatix.gParSet('optNumOfPages',int(s.parNumOfPages.Value ))
			except ValueError:
				pass
			try:
				albumatix.gParSet('optNumOfPics',int(s.parNumPics .Value))
			except ValueError:
				pass


			alb=albumatix.Album()
			alb.createAlbum()

class ABXApp(wx.App):
	def OnInit(s):
		frame = ABXFrame(None, -1, 'A L B U M A T I X')
		frame.Show(True)
		s.SetTopWindow(frame)
		return True

app = ABXApp(0)
app.MainLoop()
