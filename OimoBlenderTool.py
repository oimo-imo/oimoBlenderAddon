bl_info = {
    "name": "OimoBlenderTool",
    "author": "Your Name",
    "version": (1, 1), # バージョンを少し上げました
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > Oimo Tool",
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
        # 選択されているオブジェクトをループ処理
        for obj in context.selected_objects:
            if obj.type == 'MESH':
                # マトリックスワールドを更新して正確な座標を取得
                context.view_layer.update()
                
                # ワールド座標でのバウンディングボックスの4隅を取得
                world_corners = [obj.matrix_world @ list(corner) for corner in obj.bound_box]
                
                # その中で一番低いZ座標（底面の高さ）を見つける
                min_z = min([co.z for co in world_corners])
                
                # 現在のZ位置から、底面の高さ分を引くことで、底面を0にする
                # XとYは触らないので、その場で接地します
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
        # 編集モードかどうか確認
        if context.mode != 'EDIT_MESH':
            self.report({'WARNING'}, "編集モードで実行してください")
            return {'CANCELLED'}

        # 1. 3Dカーソルを選択物の中心（重心）にスナップ
        bpy.ops.view3d.snap_cursor_to_selected()

        # 2. オブジェクトモードに戻る
        bpy.ops.object.mode_set(mode='OBJECT')

        # 3. 原点を3Dカーソルの位置に移動
        bpy.ops.object.origin_set(type='ORIGIN_CURSOR', center='MEDIAN')

        # 4. 編集モードに戻す
        bpy.ops.object.mode_set(mode='EDIT')
        
        self.report({'INFO'}, "原点を移動しました")
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
        layout.label(text="整列ツール", icon='ALIGN_BOTTOM') # アイコンを下揃えっぽいものに変更
        row = layout.row()
        row.scale_y = 1.5
        # 修正したクラスを呼び出すボタン
        row.operator(OBJECT_OT_OimoDropToFloor.bl_idname, text="床に接地 (Z=0)")

        layout.separator()

        # --- セクション: 原点操作 ---
        layout.label(text="原点操作 (編集モード)", icon='PIVOT_CURSOR')
        row = layout.row()
        row.scale_y = 1.5
        row.operator(OBJECT_OT_OimoSetOriginToSelected.bl_idname, text="選択位置へ原点移動")


# ------------------------------------------------------------------------
#   登録処理
# ------------------------------------------------------------------------
classes = (
    OBJECT_OT_OimoDropToFloor,      # 名前を変えたのでここも更新
    OBJECT_OT_OimoSetOriginToSelected,
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