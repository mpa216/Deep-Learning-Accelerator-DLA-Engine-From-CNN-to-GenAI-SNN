"""hooks for the stage-1 spike: per-run ideal-bias scale factor (PLAN_V2 C7b: +33 % at ss/125 C, -22 % at ff/-40 C)."""


def bias_scale(corner):
    if corner.process == "ss" and corner.temp >= 100:
        return 1.33
    if corner.process == "ff" and corner.temp <= -40:
        return 0.78
    return 1.0


def prep_bias(ctx):
    return {"ibs.inc": ".param ibs = %g\n" % bias_scale(ctx["corner"])}
