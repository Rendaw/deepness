from gen_base import *
from gen_py3 import *

# TODO refcounts


def argcheck(body, method, arg, desc):
    body.write('if (!{}({}))'.format(method, arg.name))
    with body.indent():
        body.write('throw general_error_t() << "Argument [{}] is not {}.";'.format(arg.name, desc)) 


def write_python_read(body, module, el):
    out = el.name
    if isinstance(el.type, MVariant):
        first = True
        temp = next(gentemp)
        out = '{}()'.format(temp)
        body.write('auto {} = [&]()'.format(temp))
        with body.block(';'):
            for vtype in el.type.vtypes:
                pytype = module.reverse[vtype.type]
                body.write('{}if (PyObject_IsInstance({}, reinterpret_cast<PyObject *>(&{})))'.format('' if first else 'else ', el.name, pytype.typename()))
                with body.block():
                    body.write('return {}::create_{}((({} *){})->data);'.format(el.type.name, vtype.type.name, pytype.dataname(), el.name))
                first = False
            body.write('else throw general_error_t() << "Argument [{}] is not any variant of [{}].";'.format(el.name, el.type.oldname)) 
    elif isinstance(el.type, MFunctionObject):
        argcheck(body, 'PyFunction_Check', el, 'a function')
        out = next(gentemp)
        body.write('auto {} = py{}::create({});'.format(out, el.type.name, el.name))
        out = 'std::move({})'.format(out)
    elif isinstance(el.type, MClass):
        pytype = module.reverse[el.type]
        body.write('if (!PyObject_IsInstance({}, reinterpret_cast<PyObject *>(&{})))'.format(el.name, pytype.typename()))
        with body.indent():
            body.write('throw general_error_t() << "Argument [{}] is not a [{}] instance.";'.format(el.name, el.type.oldname)) 
        out = next(gentemp)
        body.write('auto {} = (({} *){})->data;'.format(out, pytype.dataname(), el.name))
        out = 'std::move({})'.format(out)
    elif isinstance(el.type, TArray):
        out = next(gentemp)
        body.write(el.type.write_var_decl(out))
        body.write('if (PyList_Check({}))'.format(el.name))
        with body.block():
            body.write('size_t size = PyList_Size({});'.format(el.name))
            body.write('{}.reserve(size);'.format(out))
            body.write('for (size_t index = 0; index < size; ++index)')
            with body.block():
                subel = MVar(name='subel', type=el.type.base)
                body.write('auto subel = PyList_GetItem({}, index);'.format(el.name))
                subout = write_python_read(body, module, subel)
                body.write('{}.emplace_back({});'.format(out, subout))
        body.write('else if (PyTuple_Check({}))'.format(el.name))
        with body.block():
            body.write('size_t size = PyTuple_Size({});'.format(el.name))
            body.write('{}.reserve(size);'.format(out))
            body.write('for (size_t index = 0; index < size; ++index)')
            with body.block():
                subel = MVar(name='subel', type=el.type.base)
                body.write('auto subel = PyTuple_GetItem({}, index);'.format(el.name))
                subout = write_python_read(body, module, subel)
                body.write('{}.emplace_back({});'.format(out, subout))
        body.write('else')
        with body.indent():
            body.write('throw general_error_t() << "Argument [{}] is not a list or tuple.";'.format(el.name)) 
    elif isinstance(el.type, (TInt32, TInt64)):
        argcheck(body, 'PyLong_Check', el, 'an integer')
        out = 'PyLong_AsLong({})'.format(el.name)
    elif isinstance(el.type, TUInt64):
        argcheck(body, 'PyLong_Check', el, 'an integer')
        out = 'PyLong_AsSize_t({})'.format(el.name)
    elif isinstance(el.type, TFloat):
        argcheck(body, 'PyFloat_Check', el, 'a float')
        out = 'PyFloat_AsDouble({})'.format(el.name)
    elif isinstance(el.type, TString):
        argcheck(body, 'PyUnicode_Check', el, 'a string')
        temp_size = next(gentemp)
        temp_buffer = next(gentemp)
        body.write('Py_ssize_t {};'.format(temp_size))
        body.write('char *{};'.format(temp_buffer))
        body.write('{} = PyUnicode_AsUTF8AndSize({}, &{});'.format(temp_buffer, el.name, temp_size))
        out = 'std::string({}, {})'.format(temp_buffer, temp_size)
    else:
        raise AssertionError('Cannot from-python element type {}'.format(el.type))
    return out


def write_python_write(body, module, el, recurse=None):
    if recurse is None:
        recurse = write_python_write
    out = next(gentemp)
    if isinstance(el.type, MVariant):
        first = True
        for vtype in el.type.vtypes:
            pytype = module.reverse[vtype.type]
            body.write('{}if ({})'.format('' if first else 'else ', MAccess(base=el, field=el.type.get_check(vtype.type)).format_call()))
            with body.block():
                body.write('auto {} = {n}.tp_new(&{n}, nullptr, nullptr);'.format(out, n=pytype.typename()))
                body.write('new (&reinterpret_cast<{} *>({})->data){}({});'.format(pytype.dataname(), out, vtype.format_type(), MAccess(base=el, field=el.type.get_get(vtype.type)).format_call()))
            first = False
        out = '(PyObject *){}'.format(out)
    elif isinstance(el.type, MClass):
        pytype = module.reverse[el.type]
        body.write('auto {} = {n}.tp_new(&{n}, nullptr, nullptr);'.format(out, n=pytype.typename()))
        body.write('new (&reinterpret_cast<{} *>({})->data){}({});'.format(pytype.dataname(), out, el.type.format_type(), el.format_read()))
        out = '(PyObject *){}'.format(out)
    elif isinstance(el.type, TArray):
        # Unused I think
        index = next(gentemp)
        body.write('auto {} = PyTuple_New({}.size());'.format(out, el.format_read()))
        body.write('for (size_t {i} = 0; {i} < {}.size(); ++{i})'.format(el.format_read(), i=index))
        with body.block():
            subin = next(gentemp)
            body.write('auto &{} = {}[{}];'.format(subin, el.format_read(), index))
            subout = write_python_write(body, module, MVar(name=subin, type=el.type.base), recurse=recurse)
            body.write('PyTuple_SetItem({}, {}, {});'.format(out, index, subout))
    elif isinstance(el.type, (TInt32, TInt64)):
        body.write('auto {} = PyLong_FromLong({});'.format(out, el.name))
    elif isinstance(el.type, TUInt64):
        body.write('auto {} = PyLong_FromSize_t({});'.format(out, el.name))
    elif isinstance(el.type, TFloat):
        body.write('auto {} = PyFloat_FromDouble({});'.format(out, el.name))
    elif isinstance(el.type, TString):
        body.write('auto {} = PyUnicode_FromStringAndSize({n}.c_str(), {n}.length());'.format(out, n=el.name))
    else:
        raise AssertionError('{} to-python unimplemented.'.format(el.type))
    return out


@simpleinit(['base', 'parent'], [])
class MPyFunction(MBase):
    def format_meta(self):
        return (
            '{' + 
            '"{}", (PyCFunction){}, {}METH_VARARGS | METH_KEYWORDS, nullptr'.format(
                self.base.name, self.name, 'METH_STATIC | ' if self.base.static else '') + 
            '},'
        )

    def format_proto(self, module):
        method = self.base
        prefix = self.parent.prefix()
        wrapper_name = ''
        wrapper_name = '{}_method_'.format(prefix)
        wrapper_name += method.name
        self.name = wrapper_name
        return 'static PyObject *{}({}PyObject *pargs, PyObject *kwargs)'.format(
            wrapper_name,
            #'PyObject *_self, ' if method.parent is not None else '',
            'PyObject *_self, ',
        )

    def write_proto(self, module):
        body = Context()
        body.write('{};'.format(self.format_proto(module)))
        return body.f

    def write_method_decl(self, module, withdefs):
        body = Context()
        method = self.base
        prefix = self.parent.prefix()
        body.write(self.format_proto(module))
        with body.block():
            body.write('try')
            with body.block():
                if method.parent:
                    body.write('auto *self = ({} *)_self;'.format(module.reverse[method.parent].dataname()))
                body.write('auto const parg_size = PyTuple_Size(pargs);')
                body.write('(void)parg_size;')
                for index, arg in enumerate(method.args):
                    body.write('PyObject *{} = nullptr;'.format(arg.name))
                    body.write('if ({} < parg_size)'.format(index))
                    with body.indent():
                        body.write('{} = PyTuple_GetItem(pargs, {});'.format(arg.name, index))
                body.write('if (kwargs != nullptr)')
                with body.block():
                    for arg in method.args:
                        with body.block():
                            body.write('PyObject *temp = PyDict_GetItemString(kwargs, "{}");'.format(arg.name, arg.name))
                            body.write('if (temp != nullptr) {} = temp;'.format(arg.name))
                for arg in method.args:
                    body.write('if ({n} == nullptr) throw general_error_t() << "Missing argument [{n}].";'.format(n=arg.name))
                vals = [write_python_read(body, module, arg) for arg in method.args]
                if method.parent is not None:
                    access = MAccess(base=MVar(name='self->data', type=method.parent), field=method)
                else:
                    access = method
                call = access.format_call(*[MVar(name=val, type=arg.type) for val, arg in zip(vals, method.args)])
                if method.ret is not None and method.ret != void:
                    body.write('auto {} = {};'.format(method.ret.name, call))
                    if isinstance(method.ret.type, MClass) and method.ret.type.identity:
                        body.write('if (!{})'.format(method.ret.name))
                        with body.block():
                            body.write('Py_INCREF(Py_None);')
                            body.write('return Py_None;')
                    out = write_python_write(body, module, method.ret)
                    body.write('return {};'.format(out))
                else:
                    body.write('{};'.format(call))
                    body.write('Py_INCREF(Py_None);')
                    body.write('return Py_None;')
            body.write('catch (general_error_t &e)')
            with body.block():
                body.write('PyErr_SetString(PyExc_RuntimeError, static_cast<std::string>(e).c_str());')
                body.write('return nullptr;')
        body.write('')
        return body.f


class MPyCallFunction(MPyFunction):
    def format_proto(self, module):
        prefix = self.parent.prefix()
        wrapper_name = '{}_method__call'.format(prefix)
        self.name = wrapper_name
        return 'static PyObject *{}(PyObject *_self, PyObject *pargs, PyObject *kwargs)'.format(wrapper_name)


@simpleinit(['name', 'type', 'parent'], ['functions'])
class MPyType(MBase):
    call = None

    def init2(self):
        for data in self.type.all_methods():
            if data.ret is None:
                continue
            if data.name == 'operator()':
                self.call = MPyCallFunction(base=data)
                self.call.parent = self
            else:
                self.add_functions(MPyFunction(base=data))

    def prefix(self):
        return '{}_type_{}'.format(self.parent.prefix(), self.name)

    def dataname(self):
        return self.prefix()

    def typename(self):
        return '{}_type'.format(self.prefix())

    def add_functions(self, function):
        function.parent = self
        self.functions.append(function)

    def write_method_decl(self, withdefs):
        mod = Context()
            
        mod.write('struct {}'.format(self.prefix()))
        with mod.block(';'):
            mod.write('PyObject_HEAD')
            mod.write(self.type.write_var_decl('data'))
        mod.write('')

        for function in self.functions:
            mod.write(function.write_proto(self.parent))
        if self.call:
            mod.write(self.call.write_proto(self.parent))

        mod.write('static PyMethodDef {}_methods[] ='.format(self.prefix()))
        with mod.block(';'):
            for function in self.functions:
                mod.write(function.format_meta())
            mod.write('{nullptr}')
        mod.write('')

        mod.write('static void {n}_dealloc({n} *self)'.format(n=self.prefix()))
        with mod.block():
            mod.write('placement_destroy(self->data);')
            mod.write('Py_TYPE(self)->tp_free(self);')
        mod.write('')

        mod.write('static PyTypeObject {}_type ='.format(self.prefix()))
        with mod.block(';'):
            mod.write('PyVarObject_HEAD_INIT(nullptr, 0)')
            mod.write('"{}.{}", /* tp_name */'.format(self.parent.name, self.name))
            mod.write('sizeof({}_type), /* tp_basicsize */'.format(self.prefix()))
            mod.write('0, /* tp_itemsize */')
            mod.write('(destructor){}_dealloc, /* tp_dealloc */'.format(self.prefix()))
            mod.write('nullptr, /* tp_print */')
            mod.write('nullptr, /* tp_getattr */')
            mod.write('nullptr, /* tp_setattr */')
            mod.write('nullptr, /* tp_reserved */')
            mod.write('nullptr, /* tp_repr */')
            mod.write('nullptr, /* tp_as_number */')
            mod.write('nullptr, /* tp_as_sequence */')
            mod.write('nullptr, /* tp_as_mapping */')
            mod.write('nullptr, /* tp_hash */')
            if self.call:
                mod.write('{}, /* tp_call */'.format(self.call.name))
            else:
                mod.write('nullptr, /* tp_call */')
            mod.write('nullptr, /* tp_str */')
            mod.write('nullptr, /* tp_getattro */')
            mod.write('nullptr, /* tp_setattro */')
            mod.write('nullptr, /* tp_as_buffer */')
            mod.write('Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE, /* tp_flags */')
            mod.write('"no class documentation", /* tp_doc */')
            mod.write('nullptr, /* tp_traverse */')
            mod.write('nullptr, /* tp_clear */')
            mod.write('nullptr, /* tp_richcompare */')
            mod.write('0, /* tp_weaklistoffset */')
            mod.write('nullptr, /* tp_iter */')
            mod.write('nullptr, /* tp_iternext */')
            mod.write('{}_methods, /* tp_methods */'.format(self.prefix()))
            mod.write('nullptr, /* tp_members */')
            mod.write('nullptr, /* tp_getset */')
            mod.write('nullptr, /* tp_base */')
            mod.write('nullptr, /* tp_dict */')
            mod.write('nullptr, /* tp_descr_get */')
            mod.write('nullptr, /* tp_descr_set */')
            mod.write('0, /* tp_dictoffset */')
            mod.write('nullptr, /* tp_init */')
            mod.write('nullptr, /* tp_alloc */')
            mod.write('nullptr, /* tp_new */')
        mod.write('')
        
        for function in self.functions:
            mod.write(function.write_method_decl(self.parent, True))
        if self.call:
            mod.write(self.call.write_method_decl(self.parent, True))

        return mod.f


@simpleinit(['name'], ['functions', 'types'])
class MPyModule(MBase):
    def __init__(self):
        self.reverse = {}

    def prefix(self):
        return 'pyint_{}'.format(self.name)

    def initname(self):
        return 'PyInit_{}'.format(self.name)

    def add_functions(self, function):
        function.parent = self
        self.functions.append(function)
    
    def add_types(self, pytype):
        pytype.parent = self
        self.reverse[pytype.type] = pytype
        self.types.append(pytype)

    def write_method_decl(self, withdefs):
        mod = Context()

        for pytype in self.types:
            mod.write('//' + '-' * 78)
            mod.write('// {}'.format(pytype.name))
            mod.write(pytype.write_method_decl(True))

        mod.write('//' + '-' * 78)
        for function in self.functions:
            mod.write(function.write_method_decl(self, True))

        mod.write('static PyMethodDef {}_methods[] ='.format(self.prefix()))
        with mod.block(';'):
            for function in self.functions:
                mod.write(function.format_meta())
            mod.write('{nullptr, nullptr}')
        mod.write('')

        mod.write('static struct PyModuleDef {}_module ='.format(self.prefix()))
        with mod.block(';'):
            mod.write('PyModuleDef_HEAD_INIT,')
            mod.write('"{}",'.format(self.name))
            mod.write('nullptr,')
            mod.write('-1,')
            mod.write('{}_methods,'.format(self.prefix()))
            mod.write('nullptr,')
            mod.write('nullptr,')
            mod.write('nullptr,')
            mod.write('nullptr')
        mod.write('')

        mod.write('extern "C" PyObject *{}(void)'.format(self.initname()))
        with mod.block():
            for pytype in self.types:
                mod.write('if (PyType_Ready(&{}_type) < 0) return nullptr;'.format(pytype.prefix()))
            mod.write('PyObject *module = PyModule_Create(&{}_module);'.format(self.prefix()))
            mod.write('if (module == nullptr)')
            with mod.indent():
                mod.write('return nullptr;')
            for pytype in self.types:
                mod.write('Py_INCREF(&{}_type);'.format(pytype.prefix()))
                mod.write('PyModule_AddObject(module, "{}", (PyObject *)&{});'.format(pytype.name, pytype.typename()))
            mod.write('return module;')
        mod.write('')
        return mod.f


def apply(name, model):
    out = []
    module = MPyModule(name=name)
    for el in model:
        if isinstance(el, MFunctionObject):
            operator = el.get_field('operator()')
            def call_body():
                body = Context()
                body.write('auto converted_args = PyTuple_New({});'.format(len(operator.args)))
                body.write('auto _clean3 = finish([&]() { Py_DECREF(converted_args); });')
                for index, arg in enumerate(operator.args):
                    newarg = write_python_write(body, module, arg)
                    body.write('PyTuple_SetItem(converted_args, {}, {});'.format(index, newarg))
                body.write('{}PyObject_CallObject(data, converted_args);'.format('{} = '.format(operator.ret.name) if operator.ret != void else ''))
                if operator.ret != void:
                    result = write_python_read(body, module, operator.ret)
                    body.write('return {};'.format(result))
                return body.f
            out.append(MClass(
                name='py{}'.format(el.oldname),
                implements=[el],
                fields=[
                    MFunction(
                        name='operator()',
                        ret=operator.ret,
                        args=operator.args,
                        body=call_body,
                    ),
                    MRawVar(
                        name='data',
                        type='PyObject *',
                        pointer=True,
                    ),
                ],
            ))
        if isinstance(el, MClass) and not isinstance(el, MVariant):
            module.add_types(MPyType(name=el.oldname, type=el))
        elif isinstance(el, MFunction):
            if el.ret is None:
                continue
            module.add_functions(MPyFunction(base=el))
    out.append(module)
    return out
