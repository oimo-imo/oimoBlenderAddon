bl_info = {
    "name": "Rename and Material Applier",
    "author": "Coding Partner",
    "version": (1, 1), # バージョンを更新
    "blender": (2, 80, 0), # Blender 2.80以上に対応
    "location": "3D View > UI Panel (Nキー) > Tool タブ",
    "description": "選択したオブジェクトのリネームとマテリアル設定を同時に行います。",
    "warning": "",
    "doc_url": "",
    "category": "Object",
}

import bpy

# ------------------------------------------------------------------------
# 1. メインの処理を行うオペレータ
# ------------------------------------------------------------------------
class OBJECT_OT_RenameAndMaterialApply(bpy.types.Operator):
    """選択オブジェクトに名前とマテリアルを適用します"""
    bl_idname = "object.rename_and_material_apply"
    bl_label = "名前とマテリアルを適用"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        obj_name_base = scene.my_tool_object_name
        mat_name = scene.my_tool_material_name
        selected_objects = context.selected_objects

        # --- ① 入力チェック ---
        if not selected_objects:
            self.report({'WARNING'}, "オブジェクトが選択されていません。")
            return {'CANCELLED'}

        if not obj_name_base and not mat_name:
            self.report({'WARNING'}, "オブジェクト名またはマテリアル名を入力してください。")
            return {'CANCELLED'}

        # --- ② マテリアル処理 ---
        material_to_apply = None
        if mat_name:
            # マテリアル名が指定されている場合
            
            # (A) 既存のマテリアルを探す
            material_to_apply = bpy.data.materials.get(mat_name)
            
            # (B) 存在しない場合は新規作成
            if not material_to_apply:
                material_to_apply = bpy.data.materials.new(name=mat_name)
                self.report({'INFO'}, f"マテリアル '{mat_name}' を新規作成しました。")

            # (C) 選択中の全オブジェクト（メッシュのみ）に適用
            for obj in selected_objects:
                if obj.type == 'MESH':
                    if obj.data.materials:
                        # 既にマテリアルスロットがある場合は、0番目を置き換える
                        obj.data.materials[0] = material_to_apply
                    else:
                        # スロットがない場合は追加する
                        obj.data.materials.append(material_to_apply)

        # --- ③ リネーム処理 ---
        if obj_name_base:
            # オブジェクト名が指定されている場合
            
            # (A) 選択オブジェクトの中で、最上位の親を特定する
            # (親がいない、または、親が選択オブジェクトに含まれていないもの)
            top_level_parents = [obj for obj in selected_objects if obj.parent is None or obj.parent not in selected_objects]
            
            if not top_level_parents:
                self.report({'WARNING'}, "リネーム対象の親オブジェクトが見つかりません。")
                # マテリアル処理だけは実行されている可能性があるので 'FINISHED' にする
            else:
                # 処理順序を安定させるためにソート
                top_level_parents.sort(key=lambda o: o.name)
                
                is_multiple_parents = len(top_level_parents) > 1
                
                for i, parent in enumerate(top_level_parents):
                    
                    # (B) 親オブジェクトのベース名を決定
                    # 親が複数選択されている場合は、親自体にも連番を振る
                    base_name = f"{obj_name_base}.{i+1:03d}" if is_multiple_parents else obj_name_base
                    parent.name = base_name
                    
                    # (C) 選択されている子孫を取得してリネーム
                    # (孫以降も含む)
                    
                    # --- ▼▼▼ エラー修正箇所 ▼▼▼ ---
                    
                    # parent のすべての子孫を取得 (parent.children_recursive)
                    all_descendants = list(parent.children_recursive)
                    
                    # 選択されているオブジェクトのうち、all_descendants に含まれるもの
                    selected_descendants = [obj for obj in selected_objects if obj in all_descendants]
                    
                    # --- ▲▲▲ エラー修正箇所 ▲▲▲ ---
                    
                    selected_descendants.sort(key=lambda o: o.name) # 順序を安定させる
                    
                    for j, child in enumerate(selected_descendants):
                        child.name = f"{base_name}.{j+1:03d}" # 例: MyObject.001

        self.report({'INFO'}, "処理が完了しました。")
        return {'FINISHED'}

# ------------------------------------------------------------------------
# 2. UIパネル
# ------------------------------------------------------------------------
class VIEW3D_PT_RenameAndMaterialPanel(bpy.types.Panel):
    """リネームとマテリアル設定を行うUIパネル"""
    bl_label = "Rename & Material" # パネルのタイトル
    bl_idname = "VIEW3D_PT_rename_material_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Tool' # 3Dビューの「Tool」タブに表示されます

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        
        box = layout.box()
        box.label(text="一括設定ツール", icon='SETTINGS')
        
        col = box.column(align=True)
        
        # (A) オブジェクト名入力欄
        col.prop(scene, "my_tool_object_name")
        
        # (B) マテリアル名入力欄
        col.prop(scene, "my_tool_material_name")
        
        layout.separator()
        
        # (C) 実行ボタン
        layout.operator(OBJECT_OT_RenameAndMaterialApply.bl_idname, icon='PLAY')

# ------------------------------------------------------------------------
# 3. プロパティの登録
# (UIで入力された値をシーンに保存するために使います)
# ------------------------------------------------------------------------
def register_properties():
    bpy.types.Scene.my_tool_object_name = bpy.props.StringProperty(
        name="オブジェクト名",
        description="設定するオブジェクトのベース名",
        default="MyObject"
    )
    bpy.types.Scene.my_tool_material_name = bpy.props.StringProperty(
        name="マテリアル名",
        description="設定・作成するマテリアル名",
        default="MyMaterial"
    )

def unregister_properties():
    del bpy.types.Scene.my_tool_object_name
    del bpy.types.Scene.my_tool_material_name

# ------------------------------------------------------------------------
# 4. アドオンの登録・解除処理
# ------------------------------------------------------------------------
classes = (
    OBJECT_OT_RenameAndMaterialApply,
    VIEW3D_PT_RenameAndMaterialPanel,
)

def register():
    register_properties()
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    unregister_properties()
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

# Blenderで直接実行した場合（テスト用）
if __name__ == "__main__":
    register()