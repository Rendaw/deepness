from gen_base import *

def apply_hxx(model, withdefs=False):
    body = Context()
    for mclass in model:
        if not isinstance(mclass, MPreRaw):
            continue
        body.write(mclass.hxx)
    for mclass in model:
        body.write(mclass.write_proto())
    body.write('')
    for mclass in model:
        if withdefs and isinstance(mclass, MClass):
            body.write('//' + '-' * 78)
            body.write('// {}'.format(mclass.name))
        body.write(mclass.write_method_decl(withdefs=withdefs))
    for mclass in model:
        if not isinstance(mclass, MPostRaw):
            continue
        body.write(mclass.hxx)
    return body.f

def apply_cxx(model):
    body = Context()
    for mclass in model:
        if not isinstance(mclass, MPreRaw):
            continue
        body.write(mclass.cxx)
    for mclass in model:
        if isinstance(mclass, MClass):
            body.write('//' + '-' * 78)
            body.write('// {}'.format(mclass.name))
            body.write('')
        body.write(mclass.write_impl())
        body.write('')
    for mclass in model:
        if not isinstance(mclass, MPostRaw):
            continue
        body.write(mclass.cxx)
    return body.f

