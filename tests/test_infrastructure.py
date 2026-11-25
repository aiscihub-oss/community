"""Guard the GitHub-native submission, category, and publication contracts."""

import re
import unittest

import yaml

from scripts import catalog


class InfrastructureTests(unittest.TestCase):
    def load_yaml(self, path):
        # GitHub uses YAML 1.2; BaseLoader preserves keys such as "on".
        return yaml.load((catalog.ROOT / path).read_text(), Loader=yaml.BaseLoader)

    def test_issue_form_categories_and_project_only_fields(self):
        form = self.load_yaml(".github/ISSUE_TEMPLATE/project-submission.yml")
        fields = {item["id"]: item for item in form["body"] if "id" in item}
        self.assertEqual(set(fields), {"project_name", "repository", "category", "summary", "license", "confirmations"})
        self.assertEqual(fields["category"]["attributes"]["options"], list(catalog.CATEGORIES.values()))
        for field in ("project_name", "repository", "category", "summary", "license"):
            self.assertEqual(fields[field]["validations"]["required"], "true")
        self.assertTrue(all(option["required"] == "true" for option in fields["confirmations"]["attributes"]["options"]))
        self.assertIn("This issue is public", form["body"][0]["attributes"]["value"])

    def test_workflows_are_read_only_and_pinned(self):
        workflows = (
            self.load_yaml(".github/workflows/validate.yml"),
            self.load_yaml(".github/workflows/refresh.yml"),
        )
        for workflow in workflows:
            with self.subTest(name=workflow["name"]):
                self.assertEqual(workflow["permissions"], {"contents": "read"})
                self.assertNotIn("pull_request_target", workflow["on"])
                self.assertNotIn("issues", workflow["on"])
                self.assertNotIn("issue_comment", workflow["on"])
                for job in workflow["jobs"].values():
                    self.assertNotIn("permissions", job)
                    for step in job["steps"]:
                        if "uses" in step:
                            self.assertRegex(step["uses"], r"^actions/[a-z-]+@[a-f0-9]{40}$")
                            if step["uses"].startswith("actions/checkout"):
                                self.assertEqual(step["with"]["persist-credentials"], "false")
                        if "run" in step:
                            self.assertNotRegex(step["run"], re.compile(r"git push|gh pr|\$\{\{"))

    def test_refresh_uses_approved_branch_and_only_two_artifact_files(self):
        workflow = self.load_yaml(".github/workflows/refresh.yml")
        self.assertEqual(set(workflow["on"]), {"schedule", "workflow_dispatch", "push"})
        refresh = workflow["jobs"]["refresh"]
        self.assertEqual(refresh["if"], "github.ref == 'refs/heads/main'")
        self.assertEqual(workflow["on"]["push"]["branches"], ["main"])
        commands = [step["run"] for step in refresh["steps"] if "run" in step]
        self.assertIn("python scripts/catalog.py refresh", commands)
        artifact = next(step for step in refresh["steps"] if step.get("uses", "").startswith("actions/upload-artifact"))
        self.assertEqual(set(artifact["with"]["path"].split()), {"PROJECTS.md", "registry/metadata.json"})

    def test_ci_runs_tests_offline_check_and_live_validation(self):
        workflow = self.load_yaml(".github/workflows/validate.yml")
        self.assertEqual(workflow["on"]["pull_request"]["branches"], ["main"])
        commands = [step["run"] for step in workflow["jobs"]["validate"]["steps"] if "run" in step]
        self.assertIn("python -m unittest discover -s tests -v", commands)
        self.assertIn("python scripts/catalog.py check", commands)
        self.assertIn("python scripts/catalog.py validate", commands)


if __name__ == "__main__":
    unittest.main()
