bl_info = {
    "name": "OimoBlenderTool",
    "author": "Your Name",
    "version": (1, 2), # バージョン更新
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > OimoTool",
    "description": "便利なショートカットとツールをまとめたアドオン",
    "category": "3D View",
}

import bpy
import bmesh

# ------------------------------------------------------------------------
#   機能1: 床に接地 (その場で底面をZ=0に合わせる)
# ------------------------------------------------------------------------
class OBJECT_OT_OimoDropToFloor(bpy.types.Operator):
    """選択したオブジェクトの位置(XY)は変えずに、底面を地面(Z=0)に合わせます"""
    bl_idname = "object.oimo_drop_to_floor"
    bl_label = "床に接地 (Drop to Floor)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        for obj in context.selected_objects:
            if obj.type == 'MESH':
                context.view_layer.update()
                world_corners = [obj.matrix_world @ list(corner) for corner in obj.bound_box]
                min_z = min([co.z for co in world_corners])
                obj.location.z -= min_z

        self.report({'INFO'}, "オブジェクトを接地しました")
        return {'FINISHED'}


# ------------------------------------------------------------------------
#   機能2: 原点調整 (編集モードの選択位置へ移動)
# ------------------------------------------------------------------------
class OBJECT_OT_OimoSetOriginToSelected(bpy.types.Operator):
    """編集モードでの選択位置(頂点・辺・面)に原点を移動"""
    bl_idname = "object.oimo_set_origin_selected"
    bl_label = "選択位置へ原点移動"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if context.mode != 'EDIT_MESH':
            self.report({'WARNING'}, "編集モードで実行してください")
            return {'CANCELLED'}

        bpy.ops.view3d.snap_cursor_to_selected()
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.origin_set(type='ORIGIN_CURSOR', center='MEDIAN')
        bpy.ops.object.mode_set(mode='EDIT')
        
        self.report({'INFO'}, "原点を移動しました")
        return {'FINISHED'}


# ------------------------------------------------------------------------
#   機能3: 3Dカーソルをワールド原点へリセット (NEW)
# ------------------------------------------------------------------------
class VIEW3D_OT_OimoResetCursor(bpy.types.Operator):
    """3Dカーソルをワールド原点(0,0,0)に戻します"""
    bl_idname = "view3d.oimo_reset_cursor"
    bl_label = "カーソルを原点へリセット"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # カーソルの位置を直接(0,0,0)に指定
        context.scene.cursor.location = (0.0, 0.0, 0.0)
        # カーソルの回転もリセットしておくと安全です
        context.scene.cursor.rotation_euler = (0.0, 0.0, 0.0)
        
        self.report({'INFO'}, "3Dカーソルをリセットしました")
        return {'FINISHED'}


# ------------------------------------------------------------------------
#   UIパネルの作成
# ------------------------------------------------------------------------
class VIEW3D_PT_OimoPanel(bpy.types.Panel):
    """サイドバーに表示されるパネル"""
    bl_label = "Oimo Blender Tool"
    bl_idname = "VIEW3D_PT_oimo_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Oimo Tool"

    def draw(self, context):
        layout = self.layout
        
        # --- セクション: 整列 ---
        layout.label(text="整列ツール", icon='ALIGN_BOTTOM')
        row = layout.row()
        row.scale_y = 1.5
        row.operator(OBJECT_OT_OimoDropToFloor.bl_idname, text="床に接地 (Z=0)")

        layout.separator()

        # --- セクション: 原点・カーソル ---
        layout.label(text="原点・カーソル操作", icon='PIVOT_CURSOR')
        
        # 原点移動 (編集モード用)
        row = layout.row()
        row.scale_y = 1.5
        row.operator(OBJECT_OT_OimoSetOriginToSelected.bl_idname, text="選択位置へ原点移動")
        
        # カーソルリセット (NEW)
        row = layout.row()
        row.scale_y = 1.2 # 少し高さを抑えめにする
        row.operator(VIEW3D_OT_OimoResetCursor.bl_idname, text="3Dカーソルをリセット", icon='CURSOR')


# ------------------------------------------------------------------------
#   登録処理
# ------------------------------------------------------------------------
classes = (
    OBJECT_OT_OimoDropToFloor,
    OBJECT_OT_OimoSetOriginToSelected,
    VIEW3D_OT_OimoResetCursor, # 追加
    VIEW3D_PT_OimoPanel,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()