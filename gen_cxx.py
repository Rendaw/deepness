from gen_base import *

def apply_hxx(model, withdefs=False):
    body = Context()
    for mclass in model:
        if not isinstance(mclass, MClass):
            continue
        body.write(mclass.write_proto())
    body.write('')
    for mclass in model:
        if withdefs:
            body.write('//' + '-' * 78)
            body.write('// {}'.format(mclass.name))
        body.write(mclass.write_method_decl(withdefs=withdefs))
    return body.f

def apply_cxx(model):
    body = Context()
    for mclass in model:
        if not isinstance(mclass, MClass):
            continue
        body.write('//' + '-' * 78)
        body.write('// {}'.format(mclass.name))
        body.write('')
        body.write(mclass.write_impl())
    return body.f

