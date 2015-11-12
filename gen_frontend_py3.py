from gen_base import *
import model
import gen_cxx
import gen_py3

# TODO helper functions read_config, read_argv
# TODO finish<>

def apply():
    module_model = [
        model.action_function,
    ]
    frontend_model = gen_py3.apply('deepness_frontend', module_model)
    module = frontend_model[0]

    def add(melement):
        frontend_model.append(melement)

    # Prototypes
    data = MRawVar(
        name='data',
        type='PyObject *',
    )
    context = MClass(
        name='pycontext',
        implements=[model.context],
        fields=[data],
        identity=True,
    )
    add(context)
    elements = []
    for element in model.elements:
        pyelement = MClass(
            name='py{}'.format(element.oldname),
            implements=[element],
            fields=[data],
            identity=True,
        )
        elements.append(pyelement)
        add(pyelement)

    # Helpers
    function_pytypes = {}
    def write_python_write(body, arg):
        if arg.type in model.elements:
            return 'reinterpret_cast<py{}>({}.get())->data'.format(arg.type.name, arg.format_read())
        return gen_py3.write_python_write(body, arg)
    
    def write_python_read(body, arg):
        if arg.type in model.elements:
            return 'py{}::create({})'.format(arg.type.name, arg.format_read())
        return gen_py3.write_python_read(body, arg)

    def write_call(body, name, ret, args, obj=None):
        body.write('auto function = PyObject_GetAttrString({}, "{}");'.format(obj.name, name))
        body.write('finish<void()> _clean2([&]() { Py_DECREF(function); });')
        body.write('if (!function) throw GeneralError() << "Function [{}] is undefined.";'.format(name))
        body.write('auto converted_args = PyTuple_New({});'.format(len(args)))
        body.write('finish<void()> _clean3([&]() { Py_DECREF(converted_args); });')
        for index, arg in enumerate(args):
            newarg = write_python_write(body, arg)
            body.write('PyTuple_SetItem(converted_args, {}, {});'.format(index, newarg))
        body.write('{}PyObject_CallObject(function, converted_args);'.format('{} = '.format(ret.name) if ret != void else ''))

    def wrap_method(method, obj):
        def body():
            body = Context()
            write_call(body, method.name, method.ret, method.args, obj=obj)
            if method.ret != void:
                result = write_python_read(body, method.ret)
                body.write('return std::move({});'.format(result))
            return body.f
        return MFunction(
            name=method.name,
            ret=method.ret,
            args=method.args,
            body=body
        )

    # Define context
    def default_body(name, ret, args):
        body = Context()
        write_call(body, name, ret, args, obj=data)
        if ret != void:
            result = write_python_read(body, ret)
            body.write('return {};'.format(MVar(name=result, type=ret.type).format_move()))
        return body.f
    add_arg = MVar(name='group', type=model.group)
    context.add_field(MFunction(
        name='add',
        ret=void,
        args=[add_arg],
        body=default_body('add', void, [add_arg]),
    ))
    do_arg = MVar(name='action', type=model.action_function)
    def do_body():
        body = Context()
        body.write('PyGILState_STATE gstate = PyGILState_Ensure();')
        write_call(body, 'do', void, [do_arg], obj=data)
        body.write('PyGILState_Release(gstate);')
        return body.f
    context.add_field(MFunction(
        name='do',
        ret=void,
        args=[do_arg],
        body=do_body,
    ))
    context.add_field(MFunction(
        name='run',
        ret=void,
        body=default_body('run', void, []),
    ))

    # Define elements + context element factory methods
    for pyelement, element in zip(elements, model.elements):
        for method in element.all_methods():
            if method.ret is None:
                continue
            pyelement.add_field(wrap_method(method, data))
        def context_body(element=element):
            body = Context()
            ret = MVar(name='out', type=element)
            write_call(body, element.name, ret, [], obj=data)
            body.write('return {}::create({});'.format(element.name, ret.format_move()))
            return body.f
        context.add_field(MFunction(
            name=element.name,
            ret=element,
            body=context_body,
        ))

    # Define open
    def open_body():
        body = Context()
        body.write('PyImport_AppendInittab("{}", &{});'.format(module.name, module.initname()))
        body.write('Py_Initialize();')
        body.write('std::string name = read_argv(args, "python3-module");')
        body.write('if (name.empty()) name = read_config("python3-module");')
        body.write('if (name.empty()) throw GeneralError() << "No specified deepness python3 frontend module; You must specify a module.";')
        body.write('PyObject *module = PyImport_Import(PyUnicode_FromString(name.c_str()));')
        body.write('if (!module) throw GeneralError() << "Couldn\'t import deepness python3 frontend module [" << name << "].";')
        #body.write('finish<void()> _clean1([&]() { Py_DECREF(module); });')
        out = MRawVar(name='out', type='PyObject *')
        write_call(body, 'open', out, model.open_sig.args, obj=MRawVar(name='module', type='PyObject *', pointer=True))
        body.write('return pycontext_t::create(std::move(out));')
        return body.f
    add(MFunction(
        name='open',
        ret=MVar(name='out', type=model.context),
        args=[MVar(name='args', type=TArray(base=string))],
        body=open_body,
    ))

    return frontend_model