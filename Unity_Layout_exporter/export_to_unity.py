# unity_layout_exporter.py の一部を修正、または全書き換えしてください
bl_info = {
    "name": "Unity Layout Exporter (World)",
    "author": "Coding Partner",
    "version": (1, 1),
    "blender": (2, 80, 0),
    "location": "View3D > Sidebar > UnitySync",
    "description": "Exports selected objects' WORLD transform data",
    "category": "Import-Export",
}

import bpy
import json
import os
import math

class OBJECT_OT_ExportLayout(bpy.types.Operator):
    bl_idname = "object.export_layout_to_unity"
    bl_label = "Export Layout JSON"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        output_filename = "layout_data.json"
        blend_file_path = bpy.data.filepath
        if not blend_file_path:
            self.report({'ERROR'}, "先に.blendファイルを保存してください")
            return {'CANCELLED'}

        directory = os.path.dirname(blend_file_path)
        output_path = os.path.join(directory, output_filename)

        data_list = []
        selected_objects = context.selected_objects

        if not selected_objects:
            self.report({'WARNING'}, "オブジェクトが選択されていません")
            return {'CANCELLED'}

        for obj in selected_objects:
            # --- 変更点: matrix_world を使用して絶対座標を取得 ---
            # ワールド座標での位置
            pos = obj.matrix_world.to_translation()
            
            # ワールド座標での回転 (クォータニオンを経由してオイラーに変換も可能だが、ここではEulerで取得)
            rot = obj.matrix_world.to_euler()
            
            # スケールだけは「ローカル」のままが安全です
            # (ワールドスケールにすると、親の回転によって歪みが生じるため)
            scl = obj.scale
            
            obj_data = {
                "name": obj.name,
                "position": [pos.x, pos.y, pos.z],
                "rotation": [math.degrees(rot.x), math.degrees(rot.y), math.degrees(rot.z)],
                "scale": [scl.x, scl.y, scl.z]
            }
            data_list.append(obj_data)

        output_data = {"items": data_list}

        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=4)
            self.report({'INFO'}, f"Export完了(World座標): {output_path}")
        except Exception as e:
            self.report({'ERROR'}, f"書き出しエラー: {str(e)}")
            return {'CANCELLED'}

        return {'FINISHED'}

class VIEW3D_PT_UnitySyncPanel(bpy.types.Panel):
    bl_label = "Unity Sync"
    bl_idname = "VIEW3D_PT_unity_sync"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'UnitySync'

    def draw(self, context):
        layout = self.layout
        layout.label(text="Export World Coords:")
        layout.operator("object.export_layout_to_unity", icon='EXPORT')

classes = (OBJECT_OT_ExportLayout, VIEW3D_PT_UnitySyncPanel)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()