import gen_cxx
import model
import gen_py3
import gen_frontend_py3

def dest(name, body):
    with open(name, 'w') as f_body:
        f_body.write('\n'.join(body))

dest('out/_deepness.hxx', gen_cxx.apply_hxx(model.model))
dest('out/_deepness.cxx', gen_cxx.apply_cxx(model.model))
dest('out/_backend_py3.cxx', gen_cxx.apply_hxx(gen_py3.apply("deepness", model.model), withdefs=True))
dest('out/_frontend_py3.cxx', gen_cxx.apply_hxx(gen_frontend_py3.apply(), withdefs=True))

