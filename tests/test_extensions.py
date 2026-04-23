import unittest
import os
import shutil
from core.ast_utils import ASTScanner
from core.skill import SkillRegistry

class TestCoreExtensions(unittest.TestCase):
    def setUp(self):
        self.test_dir = "test_workspace"
        os.makedirs(self.test_dir, exist_ok=True)
        with open(os.path.join(self.test_dir, "sample.py"), "w") as f:
            f.write("import os\nclass MyClass:\n    def method(self): pass\ndef my_func(a): return a\n")
        
        self.skills_dir = "test_skills"
        os.makedirs(os.path.join(self.skills_dir, "test-skill"), exist_ok=True)
        with open(os.path.join(self.skills_dir, "test-skill", "SKILL.md"), "w") as f:
            f.write("---\nname: test-skill\ndescription: A test skill\ntools:\n  - name: test_tool\n    description: A test tool\n---\nBody of test skill")

    def tearDown(self):
        shutil.rmtree(self.test_dir)
        shutil.rmtree(self.skills_dir)

    def test_ast_scanner(self):
        scanner = ASTScanner(root_path=self.test_dir)
        res = scanner.scan_file("sample.py")
        self.assertEqual(len(res["classes"]), 1)
        self.assertEqual(res["classes"][0]["name"], "MyClass")
        self.assertEqual(len(res["functions"]), 2) # method and my_func are both Functions in AST walk if not filtered
        
        defs = scanner.find_definitions("MyClass")
        self.assertEqual(len(defs), 1)
        self.assertEqual(defs[0]["file"], "sample.py")

    def test_skill_registry_tools(self):
        registry = SkillRegistry(skills_dir=self.skills_dir)
        tools = registry.get_all_tools()
        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0]["function"]["name"], "test_tool")
        
        catalog = registry.get_skill_catalog()
        self.assertIn("test-skill", catalog)
        self.assertIn("A test skill", catalog)

if __name__ == "__main__":
    unittest.main()
