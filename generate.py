import gen_base
import gen_cxx
import model
import gen_py3
import gen_frontend_py3

def dest(name, body):
    with open(name, 'w') as f_body:
        f_body.write('\n'.join(body))

dest('out/_deepness.hxx', gen_cxx.apply_hxx(model.model))
dest('out/_deepness.cxx', gen_cxx.apply_cxx(model.model))
backend_py3 = gen_py3.apply("deepness", model.model)
backend_py3.insert(0, gen_base.MPreRaw(
    hxx=[
        '#include <Python.h>',
        '#include "misc.hxx"',
        '#include "_deepness.hxx"',
        'using namespace deepness;',
    ],
    cxx=[]
))
dest('out/_backend_py3.cxx', gen_cxx.apply_hxx(backend_py3, withdefs=True))

frontend_py3 = gen_frontend_py3.apply()
frontend_py3.insert(0, gen_base.MPreRaw(
    hxx=[
        '#include <Python.h>',
        '#include "misc.hxx"',
        '#include "_deepness.hxx"',
        'using namespace deepness;',
    ],
    cxx=[]
))
dest('out/_frontend_py3.cxx', gen_cxx.apply_hxx(frontend_py3, withdefs=True))

