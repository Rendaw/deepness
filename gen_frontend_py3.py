from gen_base import *
import model
import gen_cxx
import gen_py3


def apply():
    module_model = [
        model.action_function,
    ]
    frontend_model = gen_py3.apply('deepness_frontend', module_model)
    module = frontend_model[-1]
    reverse = {}
        
    frontend_model.insert(0, MPreRaw(
        hxx=[
            'PyObject *pytype_{} = nullptr;'.format(element.name) for element in model.elements
        ],
        cxx=[]
    ))

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
        reverse[element] = pyelement
    add(context)

    # Helpers
    function_pytypes = {}
    def write_python_write(body, module, arg):
        if arg.type in model.elements:
            return 'reinterpret_cast<py{} *>({}.get())->data'.format(arg.type.name, arg.format_read())
        if isinstance(arg.type, MVariant):
            temp = next(gentemp)
            body.write('auto {} = [&]()'.format(temp))
            with body.block(';'):
                first = True
                for vtype in arg.type.vtypes:
                    body.write('{}if ({})'.format('' if first else 'else ', MAccess(base=arg, field=arg.type.get_check(vtype.type)).format_call()))
                    with body.block():
                        result = write_python_write(body, module, MVar(name=MAccess(base=arg, field=arg.type.get_get(vtype.type)).format_call(), type=vtype.type))
                        body.write('return {};'.format(result))
                    first = False
                body.write('else')
                with body.block():
                    body.write('// should be dead code')
                    body.write('Py_INCREF(Py_None);')
                    body.write('return Py_None;')
            return '{}()'.format(temp)
        return gen_py3.write_python_write(body, module, arg, recurse=write_python_write)
    
    def write_python_read(body, module, arg):
        if arg.type in model.elements:
            return 'py{}::create({})'.format(arg.type.name, arg.format_read())
        if isinstance(arg.type, MVariant):
            first = True
            temp = next(gentemp)
            out = '{}()'.format(temp)
            body.write('auto {} = [&]()'.format(temp))
            with body.block(';'):
                for vtype in arg.type.vtypes:
                    pytype = 'pytype_{}'.format(vtype.name)
                    pywrapper = reverse[vtype.type]
                    body.write('{}if (PyObject_IsInstance({}, reinterpret_cast<PyObject *>(&{})))'.format('' if first else 'else ', arg.name, pytype))
                    with body.block():
                        body.write('return {}::create_{}({}::create({}));'.format(
                            arg.type.name, vtype.type.name, 
                            pywrapper.name, 
                            arg.name
                        ))
                    first = False
                body.write('else throw general_error_t() << "Argument [{}] is not any variant of [{}].";'.format(arg.name, arg.type.oldname)) 
        else:
            return gen_py3.write_python_read(body, module, arg, recurse=write_python_read)
        return out

    def write_call(body, name, ret, args, obj=None):
        body.write('auto function = PyObject_GetAttrString({}, "{}");'.format(obj.name, name))
        body.write('auto _clean2 = finish([&]() { Py_DECREF(function); });')
        body.write('if (!function) throw general_error_t() << "Function [{}] is undefined.";'.format(name))
        body.write('auto converted_args = PyTuple_New({});'.format(len(args)))
        body.write('auto _clean3 = finish([&]() { Py_DECREF(converted_args); });')
        for index, arg in enumerate(args):
            newarg = write_python_write(body, module, arg)
            body.write('PyTuple_SetItem(converted_args, {}, {});'.format(index, newarg))
        body.write('auto {} = PyObject_CallObject(function, converted_args);'.format(ret.name))
        body.write('if ({} == nullptr)'.format(ret.name))
        with body.block():
            body.write('PyErr_Print();')
            body.write('throw general_error_t() << "Error in python3 frontend code.  Details logged to stderr.";')

    def wrap_method(method, obj):
        def body():
            body = Context()
            write_call(body, method.name, method.ret, method.args, obj=obj)
            if method.ret != void:
                result = write_python_read(body, module, method.ret)
                body.write('return {};'.format(result))
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
            result = write_python_read(body, module, ret)
            body.write('return {};'.format(MVar(name=result, type=ret.type).format_move()))
        return body.f
    do_arg = MVar(name='action', type=model.action_function)
    def do_body():
        body = Context()
        body.write('PyGILState_STATE gstate = PyGILState_Ensure();')
        write_call(body, 'act', void, [do_arg], obj=data)
        body.write('PyGILState_Release(gstate);')
        return body.f
    context.add_field(MFunction(
        name='act',
        ret=void,
        args=[do_arg],
        body=do_body,
    ))
    start_arg = MVar(name='group', type=model.group)
    context.add_field(MFunction(
        name='start',
        ret=void,
        args=[start_arg],
        body=default_body('start', void, []),
    ))

    # Define elements + context element factory methods
    for pyelement, element in zip(elements, model.elements):
        for method in element.all_methods():
            if method.ret is None:
                continue
            pyelement.add_field(wrap_method(method, data))
        arg = MVar(name='name', type=string)
        def context_body(element=element, pyelement=pyelement):
            body = Context()
            ret = MVar(name='out', type=element)
            write_call(body, element.name, ret, [arg], obj=data)
            body.write('return {}::create({});'.format(pyelement.name, ret.format_move()))
            return body.f
        if element in model.prime_elements:
            context.add_field(MFunction(
                name='create_' + element.oldname,
                ret=element,
                args=[arg],
                body=context_body,
            ))

    # Define open
    def open_body():
        body = Context()
        body.write('if (read_argv(args, "list", false) == "true")')
        with body.block():
            body.write('Py_Initialize();')
            body.write('PyRun_SimpleString(')
            with body.indent():
                body.write('"import pkg_resources\\n"')
                body.write('"import email\\n"')
                body.write('"import traceback\\n"')
                body.write('"seen = set()\\n"')
                body.write('"for frontend in pkg_resources.iter_entry_points(group=\'deepness_frontends\'):\\n"')
                body.write('"    if frontend.module_name in seen:\\n"')
                body.write('"        continue\\n"')
                body.write('"    seen.add(frontend.module_name)\\n"')
                body.write('"    try:\\n"')
                body.write('"        frontend_dist = pkg_resources.get_distribution(frontend.module_name)\\n"')
                body.write('"        frontend_meta = dict(email.message_from_string(frontend_dist.get_metadata(\'PKG-INFO\')).items())\\n"')
                body.write('"        print(\'\\t{}\\t{}\\t{}\\t{}\'.format(frontend.name, frontend_dist.project_name, frontend_meta[\'Summary\'], frontend.module_name))\\n"')
                body.write('"    except Exception as e:\\n"')
                body.write('"        traceback.print_exc()\\n"')
                body.write('"if not seen:\\n"')
                body.write('"    print(\'\\t(no submodules)\')\\n"')
            body.write(');')
            body.write('return {};')
        body.write('std::vector<wchar_t *> argv;')
        body.write('argv.reserve(args.size());')
        body.write('for (auto &arg : args) argv.push_back(Py_DecodeLocale(arg.c_str(), nullptr));')
        body.write('if (!args.empty()) Py_SetProgramName(argv[0]);')
        body.write('PyImport_AppendInittab("{}", &{});'.format(module.name, module.initname()))
        body.write('Py_Initialize();')
        body.write('PySys_SetArgv(args.size(), &argv[0]);')
        body.write('for (auto &arg : argv) PyMem_RawFree(arg);')
        body.write('std::string name = read_argv(args, "python3-module");')
        body.write('if (name.empty()) name = read_config("python3-module");')
        body.write('if (name.empty()) throw general_error_t() << "No specified deepness python3 frontend module; You must specify a module.";')
        body.write('PyObject *module = PyImport_Import(PyUnicode_FromString(name.c_str()));')
        body.write('if (!module) throw general_error_t() << "Couldn\'t import deepness python3 frontend module [" << name << "].";')
        for element in model.elements:
            body.write('pytype_{n} = PyObject_GetAttrString(module, "{n}");'.format(n=element.name))
        body.write('return pycontext_tt::create(module);')
        return body.f
    add(MFunction(
        name='deepness_open',
        ret=MVar(name='out', type=model.context),
        args=[MVar(name='args', type=TArray(base=string))],
        body=open_body,
        export=True,
    ))

    return frontend_model
