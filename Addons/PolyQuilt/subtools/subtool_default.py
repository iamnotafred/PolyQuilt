# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTIBILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

import bpy
import math
import mathutils
import bmesh
import bpy_extras
import collections
import copy
from ..utils import pqutil
from ..utils import draw_util
from ..QMesh import *
from ..utils.mouse_event_util import ButtonEventUtil, MBEventType
from .subtool import *
from .subtool_makepoly import *
from .subtool_knife import *
from .subtool_edge_slice import *
from .subtool_edgeloop_cut import *
from .subtool_edge_extrude import *
from .subtool_vert_extrude import *
from .subtool_move import *
from .subtool_fin_slice import *
from .subtool_polypen import *

class SubToolDefault(SubToolRoot) :
    name = "DefaultSubTool"

    def __init__(self,op,currentTarget, button) :
        super().__init__(op, button)        
        self.currentTarget = currentTarget
        self.LMBEvent = ButtonEventUtil( button , self , SubToolDefault.LMBEventCallback , op , True )
        self.isExit = False

    def is_animated( self , context ) :
        return self.LMBEvent.is_animated()

    @staticmethod
    def LMBEventCallback(self , event ):
        self.debugStr = str(event.type)

        if event.type == MBEventType.Release :
            self.isExit = True

        elif event.type == MBEventType.Click :
            if self.currentTarget.isVert or self.currentTarget.isEmpty or self.currentTarget.isEdge:
                self.SetSubTool( SubToolMakePoly(self.operator,self.currentTarget , self.mouse_pos ) )

        elif event.type == MBEventType.LongClick :
            if self.currentTarget.isVert :
                self.bmo.dissolve_vert( self.currentTarget.element , False , False , dissolve_vert_angle=self.preferences.vertex_dissolve_angle  )
            elif self.currentTarget.isEdge :
                self.bmo.dissolve_edge( self.currentTarget.element , use_verts = False , use_face_split = False , dissolve_vert_angle=self.preferences.vertex_dissolve_angle )
            elif self.currentTarget.isFace :
                self.bmo.Remove( self.currentTarget.element )
            self.bmo.UpdateMesh()
            self.currentTarget = ElementItem.Empty()

        elif event.type == MBEventType.LongPressDrag :
            if self.currentTarget.isEdge :
                tools = []
                if SubToolPolyPen.Check( self ,self.currentTarget) : 
                    tools.append(SubToolPolyPen(self.operator,self.currentTarget))
                else :
                    if len(self.currentTarget.element.link_faces) > 0 :
                        tools.append(SubToolEdgeSlice(self.operator,self.currentTarget))
                    if SubToolEdgeloopCut.Check( self ,self.currentTarget) : 
                        tools.append(SubToolEdgeloopCut(self.operator,self.currentTarget))
                    if SubToolEdgeExtrude.Check( self ,self.currentTarget) : 
                        tools.append(SubToolEdgeExtrude(self.operator,self.currentTarget,False))
                self.SetSubTool( tools )
            elif self.currentTarget.isVert :
                tools = []
                tools.append(SubToolFinSlice(self.operator,self.currentTarget ))
                if SubToolVertExtrude.Check( self ,self.currentTarget ) :
                    tools.append(SubToolVertExtrude(self.operator,self.currentTarget))
                self.SetSubTool( tools )
            elif self.currentTarget.isEmpty :
                self.SetSubTool( SubToolKnife(self.operator, self.LMBEvent.PressPos ) )   

        elif event.type == MBEventType.Drag :
            if self.currentTarget.isEdge :
                if self.currentTarget.can_extrude() :
                    self.SetSubTool( SubToolEdgeExtrude(self.operator,self.currentTarget , False ) )
                else :
                    self.SetSubTool( SubToolMove(self.operator,self.currentTarget , self.mouse_pos ) )
            elif self.currentTarget.isNotEmpty :
                self.SetSubTool( SubToolMove(self.operator,self.currentTarget , self.mouse_pos ) )
            else :
                if self.preferences.space_drag_op == "ORBIT" :
                    bpy.ops.view3d.rotate('INVOKE_DEFAULT', use_cursor_init=True)
                    self.isExit = True
                elif self.preferences.space_drag_op == "PAN" :
                    bpy.ops.view3d.move('INVOKE_DEFAULT', use_cursor_init=True)
                    self.isExit = True
                elif self.preferences.space_drag_op == "DOLLY" :
                    bpy.ops.view3d.zoom('INVOKE_DEFAULT', use_cursor_init=True)
                    self.isExit = True
                elif self.preferences.space_drag_op == "KNIFE" :
                    self.SetSubTool( SubToolKnife(self.operator, self.LMBEvent.PressPos ) )
                elif self.preferences.space_drag_op == "SELECT_BOX" :
                    bpy.context.window.cursor_warp( event.PressPrevPos.x , event.PressPrevPos.y )
                    bpy.ops.view3d.select_box('INVOKE_DEFAULT' ,wait_for_input=False, mode='SET')
                    bpy.context.window.cursor_warp( event.event.mouse_prev_x ,event.event.mouse_prev_y )
                    self.isExit = True
                elif self.preferences.space_drag_op == "SELECT_LASSO" :
                    bpy.context.window.cursor_warp( event.PressPrevPos.x , event.PressPrevPos.y )
                    bpy.ops.view3d.select_lasso('INVOKE_DEFAULT' , path = [], mode='SET')
                    bpy.context.window.cursor_warp( event.event.mouse_prev_x ,event.event.mouse_prev_y )
                    self.isExit = True
                else :
                    self.isExit = True

    def OnUpdate( self , context , event ) :
        if self.isExit :
            return 'FINISHED'

#        if event.type == 'MOUSEMOVE' and self.LMBEvent.Press == False :
#            self.currentTarget = self.bmo.PickElement( self.mouse_pos , self.preferences.distance_to_highlight )

        self.LMBEvent.Update(context,event)

        return 'RUNNING_MODAL'

    @classmethod
    def DrawHighlight( cls , gizmo , element ) :
        if element != None and gizmo.bmo != None :
            def Draw() :
                element.Draw( gizmo.bmo.obj , gizmo.preferences.highlight_color , gizmo.preferences , True )
            return Draw
        return None

    def OnDraw( self , context  ) :
        if self.LMBEvent.isPresure :
            if self.currentTarget.isNotEmpty :
                self.LMBEvent.Draw( self.currentTarget.coord )
            else:
                self.LMBEvent.Draw( None )

    def OnDraw3D( self , context  ) :
        if self.currentTarget.isNotEmpty :
            color = self.color_highlight()
            if self.LMBEvent.is_hold :
                color = self.color_delete()
            self.currentTarget.Draw( self.bmo.obj , color , self.preferences )

    def OnEnterSubTool( self ,context,subTool ):
        self.currentTarget = ElementItem.Empty()
        self.LMBEvent.Reset(context)

    def OnExitSubTool( self ,context,subTool ):
        self.currentTarget = ElementItem.Empty() # self.bmo.PickElement( self.mouse_pos , self.preferences.distance_to_highlight )

    def OnExit( self ) :
        pass
