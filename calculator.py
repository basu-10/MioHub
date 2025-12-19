from dataclasses import dataclass
import re
import math

@dataclass
class Calculator:
    expression: str

    def sanitize(self) -> str:
        # Allow only digits, operators, decimal, brackets, and supported words
        return re.sub(r'[^0-9+\-*/().%^a-zA-Z|]', '', self.expression)

    def evaluate(self) -> str:
        expr = self.sanitize()
        expr = expr.replace('^', '**')  # Replace ^ with Python power operator
        expr = expr.replace('|', ',')  # 👈 custom delimiter fix


        # Safe math context
        allowed = {
            'sqrt': math.sqrt,
            'cbrt': lambda x: x ** (1/3),
            'log': math.log10,
            'ln': math.log,
            'pi': math.pi,
            'e': math.e,
            # 👇 CUSTOM FUNCTIONS
        'profit': lambda cp, sp: (sp - cp) / cp if cp != 0 else 'Error',
        'tax': lambda amount, rate: (amount * rate / 100),
        'markup': lambda cp, percent: cp + (cp * percent / 100),
        }

        try:
            result = eval(expr, {"__builtins__": None}, allowed)
            # Round to avoid floating point precision issues
            if isinstance(result, float):
                result = round(result, 10)  # Remove tiny floating point errors
                # Then round to reasonable display precision
                if result == int(result):
                    result = int(result)  # Show 5.0 as 5
            return str(result)
        except Exception:
            return "Error"