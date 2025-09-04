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
from GlyphsApp import Glyphs, GSEditViewController, GSFont, GSPath, GSNode, GSAnchor, GSComponent, GSHint, UPDATEINTERFACE, LINE, OFFCURVE
from GlyphsApp.plugins import PalettePlugin
from operator import itemgetter
from AppKit import NSEvent, NSEventModifierFlagCommand, NSEventModifierFlagOption
from copy import copy

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
		if isinstance(sentObject, GSEditViewController):
			currentTab = sentObject
			if not isinstance(currentTab.parent, GSFont):
				return
			font = currentTab.parent.font()
		elif isinstance(sentObject, GSFont):
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

	@objc.python_method
	def backupAllLayersOfGlyph(self, glyph):
		for layer in glyph.layers:
			if layer.isMasterLayer:
				layer.contentToBackgroundCheckSelection_keepOldBackground_(False, False)
				layer.background = layer.background.copyDecomposedLayer()

	# Action triggered by UI
	@objc.IBAction
	def eraseSelectedItemsOnAllMasters_(self, sender=None):
		try:
			keysPressed = NSEvent.modifierFlags()
			shouldBackupFirst = keysPressed & NSEventModifierFlagCommand == NSEventModifierFlagCommand
			shouldBreakPath = keysPressed & NSEventModifierFlagOption == NSEventModifierFlagOption

			# get current font
			font = Glyphs.font
			if font:
				# We’re in the Edit View
				if font.currentTab and len(font.selectedLayers) == 1:
					currentLayer = font.selectedLayers[0]
					thisGlyph = currentLayer.parent
					if shouldBackupFirst:
						self.backupAllLayersOfGlyph(thisGlyph)

					# collect selected items:
					pathNodeIndexes = []
					anchorNames = []
					componentIndexes = []
					hintIDs = []

					for thisItem in currentLayer.selection:
						if isinstance(thisItem, GSNode):
							pathNodeIndexes.append(
								currentLayer.indexPathOfNode_(thisItem)
							)
						elif isinstance(thisItem, GSAnchor):
							anchorNames.append(
								thisItem.name
							)
						elif isinstance(thisItem, GSComponent):
							componentIndexes.append(
								thisItem.elementIndex()
							)
						elif isinstance(thisItem, GSHint):
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
							key=itemgetter(0, 1),
							reverse=True,
						)
						currentCS = currentLayer.compareString()
						allCompatibleLayers = [
							l for l in thisGlyph.layers
							if (l.isMasterLayer or l.isSpecialLayer)
							and (l.compareString() == currentCS)
						]

						thisGlyph.beginUndo()  # begin undo grouping
						removePaths = list()
						for thisLayer in allCompatibleLayers:
							
							# NODES
							removeNodes = list()
							for pathNodeIndex in pathNodeIndexes:
								node = thisLayer.nodeAtIndexPath_(pathNodeIndex)
								removeNodes.append(node)

							if not shouldBreakPath:
								if len(removeNodes) == 1:
									node = removeNodes[0]
									path = node.parent
									path.removeNodeCheckKeepShape_normalizeHandles_(node, True)
									if len(path) == 0:
										removePaths.append(path)
								else:
									for node in removeNodes:
										path = node.parent
										if path is None or node not in path.nodes:  # may have been removed already
											continue
										path.removeNodeCheckKeepShape_normalizeHandles_(node, True)
										if len(path.nodes) == 0:
											removePaths.append(path)
							else:
								# user held down OPTION key, so break path:
								while removeNodes:
									first = removeNodes.pop(-1)
									last = first
									path = first.parent

									# expand to contiguous node selection:
									while first.prevNode is not None and first.prevNode in removeNodes:
										removeNodes.remove(first.prevNode)
										first = first.prevNode
									while last.nextNode is not None and last.nextNode in removeNodes:
										removeNodes.remove(last.nextNode)
										last = last.nextNode

									# if first is path.previousOncurveNodeFromIndex_(last.index):
									if first != last and first.type != OFFCURVE and last.type != OFFCURVE:
										# full segment(s) selected
										nextOn = last
										prevOn = first
									else:
										nextOn = path.nextOncurveNodeFromIndex_(last.index)
										prevOn = path.previousOncurveNodeFromIndex_(first.index)

									if path.closed:
										# set new start node and open path:
										path.makeNodeFirst_(nextOn)
										path.setClosePath_fixStartNode_(0, 1)
										# delete nodes:
										deleteme = path.nodes[-1]
										while path.nodes and deleteme != prevOn:
											del path.nodes[-1]
											deleteme = path.nodes[-1]
									else:
										# split up (open) path in two or three paths:
										splitIndex = prevOn.index
										if splitIndex > 0:
											splitPath = GSPath()
											for i in range(splitIndex+1):
												splitNode = path.nodes[i]
												splitPath.nodes.append(splitNode)
											thisLayer.shapes.append(splitPath)

										splitIndex = nextOn.index
										lastIndex = len(path.nodes) - 1
										if splitIndex < lastIndex:
											splitPath = GSPath()
											for i in range(lastIndex, splitIndex-1, -1):
												splitNode = path.nodes[i]
												splitPath.nodes.insert(0, splitNode)
											splitPath.nodes[0].type = LINE
											thisLayer.shapes.append(splitPath)
										
										removePaths.append(path)

							# ANCHORS
							for anchorName in anchorNames:
								thisLayer.removeAnchorWithName_(anchorName)

							# COMPONENTS
							for componentIndex in sorted(componentIndexes, reverse=True):
								if Glyphs.versionNumber >= 3:
									# GLYPHS 3
									del thisLayer.shapes[componentIndex]
								else:
									# GLYPHS 2
									del thisLayer.components[componentIndex]

							# CORNERS AND CAPS
							if hintIDs:
								for hintIndex in sorted(range(len(thisLayer.hints)), reverse=True):
									if hintID(thisLayer.hints[hintIndex]) in hintIDs:
										thisLayer.removeHint_(thisLayer.hints[hintIndex])

						# EMPTY PATHS (left over after removing all nodes)
						for path in removePaths:
							respectiveLayer = path.parent
							respectiveLayer.removeShape_(path)

						thisGlyph.endUndo()   # end undo grouping
		except Exception as e:
			Glyphs.clearLog()  # clears macro window log
			print("Magic Remover Exception:")
			print(e)
			print("\nMagic Remover Traceback:")
			import traceback
			print(traceback.format_exc())

	@objc.python_method
	def __file__(self):
		"""Please leave this method unchanged"""
		return __file__
