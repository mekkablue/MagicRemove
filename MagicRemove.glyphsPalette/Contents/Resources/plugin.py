# encoding: utf-8
from __future__ import division, print_function, unicode_literals

###########################################################################################################
#
#
#	Palette Plugin
#
#	Read the docs:
#	https://github.com/schriftgestalt/GlyphsSDK/tree/master/Python%20Templates/Palette
#
#
###########################################################################################################

import objc
from GlyphsApp import *
from GlyphsApp.plugins import *
from operator import itemgetter

def hintID(h):
	return (h.name, h.origin, h.target, h.other1, h.other2)

class MagicRemover (PalettePlugin):
	dialog = objc.IBOutlet()
	EraseButton = objc.IBOutlet()

	@objc.python_method
	def settings(self):
		self.name = Glyphs.localize({
			'en': 'Magic Remover',
			'de': 'Magic-Löscher',
			'es': 'Borrador magico',
			'fr': 'Gomme magique',
			'pt': 'Apagador mágico',
			'it': 'Cancellatore magico',
		})
		
		# Load .nib dialog (without .extension)
		self.loadNib('IBdialog', __file__)

	@objc.python_method
	def start(self):
		# Adding a callback for the 'GSUpdateInterface' event
		Glyphs.addCallback(self.update, UPDATEINTERFACE)

	@objc.python_method	
	def __del__(self):
		Glyphs.removeCallback(self.update)

	@objc.python_method
	def update(self, sender):
		button = self.EraseButton

		# Extract font from sender
		currentTab, font = None, None
		sentObject = sender.object()
		if sentObject is None:
			return
		if sentObject.isKindOfClass_(GSEditViewController):
			currentTab = sentObject
			font = currentTab.parent.font()
		elif sentObject.isKindOfClass_(GSFont):
			font = sentObject
			currentTab = font.currentTab
			
		# We’re in the Edit View
		if currentTab:
			if font.selectedLayers and len(font.selectedLayers) == 1:
				if font.selectedLayers[0].selection:
					button.setEnabled_(True)
					return
		
		# default: disable button
		button.setEnabled_(False)
		return
		
	# Action triggered by UI
	@objc.IBAction
	def eraseSelectedItemsOnAllMasters_(self, sender=None):
		try:
			# get current font
			font = Glyphs.font
			if font:
				# We’re in the Edit View
				if font.currentTab and len(font.selectedLayers) == 1:
					currentLayer = font.selectedLayers[0]
				
					# collect selected items:
					pathNodeIndexes = []
					anchorNames = []
					componentIndexes = []
					hintIDs = []
					
					for thisItem in currentLayer.selection:
						if type(thisItem) == GSNode:
							pathNodeIndexes.append(
								currentLayer.indexPathOfNode_(thisItem)
							)
						elif type(thisItem) == GSAnchor:
							anchorNames.append(
								thisItem.name
							)
						elif type(thisItem) == GSComponent:
							componentIndexes.append(
								thisItem.elementIndex()
							)
						elif type(thisItem) == GSHint:
							if thisItem.isCorner:
								hintIDs.append(
									hintID(thisItem)
								)
					
					# delete respective items on all (compatible) layers:
					if pathNodeIndexes or anchorNames or componentIndexes or hintIDs:
					
						# reverse-sort path and node indexes
						# so deletion of nodes does not mess with the indexes of the next node to be deleted
						pathNodeIndexes = sorted( 
							pathNodeIndexes, 
							key=itemgetter(0,1), 
							reverse=True,
						)
	
						currentCS = currentLayer.compareString()
						thisGlyph = currentLayer.parent
						allCompatibleLayers = [l for l in thisGlyph.layers 
									if (l.isMasterLayer or l.isSpecialLayer)
									and (l.compareString() == currentCS)
									]
					
						thisGlyph.beginUndo() # begin undo grouping
					
						for thisLayer in allCompatibleLayers:
							for pathNodeIndex in pathNodeIndexes:
								pathIndex, nodeIndex = pathNodeIndex[0], pathNodeIndex[1]
								path = thisLayer.paths[pathIndex]
								node = thisLayer.nodeAtIndexPath_(pathNodeIndex)
								path.removeNodeCheckKeepShape_normalizeHandles_(node,True)
							for anchorName in anchorNames:
								thisLayer.removeAnchorWithName_(anchorName)
							for componentIndex in sorted(componentIndexes, reverse=True):
								thisLayer.removeComponentAtIndex_(componentIndex)
							if hintIDs:
								for hintIndex in sorted(range(len(thisLayer.hints)), reverse=True):
									if hintID(thisLayer.hints[hintIndex]) in hintIDs:
										thisLayer.removeHint_(thisLayer.hints[hintIndex])
			
						thisGlyph.endUndo()   # end undo grouping
		except Exception as e:
			Glyphs.clearLog() # clears macro window log
			print("Magic Remover Exception:")
			print(e)
			print("\nMagic Remover Traceback:")
			import traceback
			print(traceback.format_exc())

	@objc.python_method
	def __file__(self):
		"""Please leave this method unchanged"""
		return __file__
