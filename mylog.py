# copyright Stephan Herschel - 2009-2011

import inspect
import logging

class MyLogging:
	"""
	logging mixin
	"""
	logging=True
	
	def logstart(s):
		"""
		starten des logs
		"""
		debug=False
		if debug:
			logging.basicConfig(level=logging.DEBUG,
							format='%(asctime)s %(levelname)s %(message)s',
						filename='albumatix.log',
						filemode='w')
		else:
			logging.basicConfig(level=logging.INFO,
						format='%(levelname)s %(message)s',
						filename='albumatix.log',
						filemode='w')

	def  logdbg(s, pFrame):
		"""
		schreibt einen debug-logentry
		pFrame ... inspect.currentframe()
		"""
		if s.logging:
			logging.debug(str(s.__class__)+'.'+
				inspect.getframeinfo(pFrame)[2]+
				str(inspect.getargvalues(pFrame)[3]) )

	def loginfo(s, pInf):
		"""
		schreibt einen info-logentry
		"""
		if s.logging:
			logging.info(pInf)
		
	def logerr(s, pInf):
		"""
		schreibt einen info-logentry
		"""
		if s.logging:
			logging.error(pInf)
