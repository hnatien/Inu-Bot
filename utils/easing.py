"""
Easing functions for animations, adapted from https://easings.net/
These functions take a progress value 'x' (from 0 to 1) and return a transformed value.
"""

def ease_out_bounce(x: float) -> float:
    """
    Creates a bouncing effect at the end of the animation.
    """
    n1 = 7.5625
    d1 = 2.75

    if x < 1 / d1:
        return n1 * x * x
    if x < 2 / d1:
        x -= 1.5 / d1
        return n1 * x * x + 0.75
    if x < 2.5 / d1:
        x -= 2.25 / d1
        return n1 * x * x + 0.9375

    x -= 2.625 / d1
    return n1 * x * x + 0.984375

def ease_in_cubic(x: float) -> float:
    """
    Creates a slow start, fast middle acceleration.
    """
    return x * x * x 