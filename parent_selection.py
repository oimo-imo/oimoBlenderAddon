import bpy

bl_info = {
     "name": "Parent Selection",
     "author": "subsleepics",
     "version": (0, 0, 1),
     "location": "3D View",
     "description": "親子関係選択",
     "warning": "開発中",
     "category": "Object"
 }

def select_hierarchy():
    selected_objects = bpy.context.selected_objects
    if not selected_objects:
        return
    
    bpy.ops.object.select_all(action='DESELECT')
    
    for obj in selected_objects:
        # 親を選択
        if obj.parent:
            obj.parent.select_set(True)
        
        # 子オブジェクトを再帰的に選択
        def select_children_recursive(parent):
            for child in parent.children:
                child.select_set(True)
                select_children_recursive(child)
        
        select_children_recursive(obj)
        
        # 自身を再選択
        obj.select_set(True)

class OBJECT_OT_select_parent_hierarchy(bpy.types.Operator):
    """親子関係を選択"""
    bl_idname = "object.select_parent_hierarchy"
    bl_label = "親子関係選択"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        select_hierarchy()
        return {'FINISHED'}

# コンテキストメニューに追加
def menu_func(self, context):
    self.layout.operator(OBJECT_OT_select_parent_hierarchy.bl_idname, text="親子関係選択")

def register():
    bpy.utils.register_class(OBJECT_OT_select_parent_hierarchy)
    bpy.types.VIEW3D_MT_object_context_menu.append(menu_func)

def unregister():
    bpy.utils.unregister_class(OBJECT_OT_select_parent_hierarchy)
    bpy.types.VIEW3D_MT_object_context_menu.remove(menu_func)

if __name__ == "__main__":
    register()
