import unittest

import cli


class ParseArgsTests(unittest.TestCase):
    def test_requires_template_theme_name_date(self):
        with self.assertRaises(SystemExit):
            cli.parse_args(["--theme", "Autumn", "--name", "John", "--date", "2026-09-15"])

    def test_accepts_minimal_required_arguments(self):
        args = cli.parse_args([
            "--template", "template.xcf",
            "--theme", "Autumn",
            "--name", "John",
            "--date", "2026-09-15",
        ])

        self.assertEqual(args.template, "template.xcf")
        self.assertEqual(args.title, "")
        self.assertEqual(args.title_json, "")
        self.assertEqual(args.output, "")
        self.assertEqual(args.gimp_console, cli.DEFAULT_GIMP_CONSOLE)


class BuildBatchCommandTests(unittest.TestCase):
    def _args(self, **overrides):
        base = dict(
            template="template.xcf", title="Hello", title_json="", theme="Autumn",
            name="John", date="2026-09-15", output="",
        )
        base.update(overrides)
        return cli.parse_args([
            "--template", base["template"],
            "--title", base["title"],
            "--title-json", base["title_json"],
            "--theme", base["theme"],
            "--name", base["name"],
            "--date", base["date"],
            "--output", base["output"],
        ])

    def test_wraps_call_in_procedure_name(self):
        command = cli.build_batch_command(self._args())

        self.assertTrue(command.startswith(f"({cli.BATCH_PROCEDURE} "))
        self.assertTrue(command.endswith(")"))

    def test_escapes_backslashes_and_quotes_in_paths(self):
        command = cli.build_batch_command(self._args(template=r'C:\Templates\a "weird" file.xcf'))

        self.assertIn(r'C:\\Templates\\a \"weird\" file.xcf', command)

    def test_includes_all_fields(self):
        command = cli.build_batch_command(self._args(title="Woodworking\nCourse"))

        self.assertIn('"template.xcf"', command)
        self.assertIn('"Woodworking\nCourse"', command)
        self.assertIn('"Autumn"', command)
        self.assertIn('"John"', command)
        self.assertIn('"2026-09-15"', command)

    def test_uses_named_not_positional_arguments(self):
        # Script-Fu warns that positional (ordered list) PDB calls are
        # deprecated; #:key syntax is the recommended replacement.
        command = cli.build_batch_command(self._args())

        for keyword in ("template", "title", "title-json", "theme", "name", "date", "output"):
            self.assertIn(f"#:{keyword} ", command)


if __name__ == "__main__":
    unittest.main()
