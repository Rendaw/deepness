from model import *

# TODO array2d?

def build_notify(mclass, method, *params):
    listener_func = MFunction(
        name='',
        ret=void,
        args=MArgs(args=params),
    )
    listeners = MRawVar(
        name='listeners_{}'.format(method.name), 
        type='std::map<uint16_t, {}>'.format(listener_func.format_type()),
        private=True,
        noserialize=True,
    )
    mclass.add_data(listeners)
    listener_count = MVar(
        name='listeners_{}_count'.format(method.name), 
        type=TInt32(),
        private=True,
        noserialize=True,
    )
    listener_count.constructor = [
        '{} = 0;'.format(listener_count.name)
    ]
    mclass.add_data(listener_count)

    listener_id = MVar(name='listener_id', type=listener_count.type)
    listener = MVar(name='listener', type=listener_func)
    add_listener = MFunction(
        name='{}_listener_add'.format(method.name),
        ret=listener_id,
        args=MArgs(args=[listener]),
        body=[
            'auto out = ++{};'.format(listener_count.name),
            '{}.emplace_back(out, {});'.format(listeners.name, listener.format_move()),
            'return out;',
        ],
        writelua=True,
    )
    mclass.add_method(add_listener)
    remove_listener = MFunction(
        name='{}_listener_remove'.format(method.name),
        ret=void,
        args=MArgs(args=[listener_id]),
        body=[
            'auto erased = {}.erase({});'.format(listeners.name, listener_id.name),
            'if (erased < 1) throw GeneralError() << "Trying to remove unregistered listener (id " << {} << ").";'.format(listener_id.name),
        ],
        writelua=True,
    )
    mclass.add_method(remove_listener)

    def notify_body():
        body = Context()
        body.write('for (auto &listener : {})'.format(listeners.format_read()))
        with body.indent():
            body.write('listener({});'.format(', '.join(param.format_read() for param in params)))
        return body.f
    mclass.add_method(MFunction(
        name='{}_notify'.format(method.name),
        ret=void,
        args=method.args,
        private=True,
        body=notify_body,
    ))

    return 'notify({});'.format(', '.join(param.format_read() for param in params))


def apply():
    for mclass in model.values():
        if not isinstance(mclass, MClass):
            continue
        for notify in mclass.notifications:
            build_notify(mclass, notify, *notify.args.args)
        for prop in mclass.props:
            discardable = isinstance(prop.type, MClass) and prop.type.is_shared() and not (mclass == model['project'] and prop.name == 'discards')
            mclass.add_data(prop)
            level = MVar(name='level', type=model['undolevel'])
            source_index = MVar(name='source', type=TUInt64())
            dest_index = MVar(name='dest', type=TUInt64())
            
            def handle_discard_add(body, name):
                if discardable:
                    body.write('auto is_discarded = {}->usage_decrement();'.format(name))
                    body.write('if (is_discarded)')
                    with body.block():
                        body.write('project.discard_add(level, std::move({})));'.format(name))

            def handle_discard_remove(body, name):
                if discardable:
                    body.write('auto found_discard = std::find(project.discards.begin(), project.discards.end(), {});'.format(name))
                    body.write('auto was_discard = found_discard != project.discards.end();')
                    body.write('if (was_discard)')
                    with body.block():
                        body.write('project.discards_remove(level, found_discard - project.discards.begin());')
                        body.write('{}->usage_increment();'.format(name))
                    
            if isinstance(prop.type, TArray):
                element = MVar(name='element', type=prop.type.base)
                add_method = MFunction(
                    name='{}_add'.format(prop.name),
                    ret=void,
                    args=MArgs(
                        args=(
                            level,
                            dest_index,
                            element,
                        ),
                    ),
                    writelua=True,
                )
                remove_method = MFunction(
                    name='{}_remove'.format(prop.name),
                    ret=void,
                    args=MArgs(
                        args=(
                            level,
                            dest_index,
                        ),
                    ),
                    writelua=True,
                )
                order_method = MFunction(
                    name='{}_order'.format(prop.name),
                    ret=void,
                    args=MArgs(
                        args=(
                            level,
                            dest_index,
                            source_index,
                        ),
                    ),
                    writelua=True,
                )

                def add_body():
                    body = Context()

                    # check
                    body.write('if (dest > {}.size())'.format(prop.name))
                    with body.indent():
                        body.write('throw LuaError() << "Trying to insert element beyond end (dest " << dest << ", length " << {}.size() << ").";'.format(prop.name))
                    
                    # save undo
                    body.write('level.add(std::make_shared<function_reaction_t>(')
                    with body.indent():
                        body.write('[this, dest_index](std::shared_ptr<undo_level_t> level)')
                    with body.block():
                        body.write('{}(level, dest);'.format(remove_method.name))

                    # modify
                    handle_discard_remove(body, 'element')
                    body.write('{}.insert(dest, std::move(element));'.format(prop.name))

                    # notify
                    body.write(build_notify(mclass, add_method, dest_index))

                    return body.f
                add_method.body = add_body()
                def remove_body():
                    body = Context()

                    # check
                    body.write('if (dest >= {}.size())'.format(prop.name))
                    with body.indent():
                        body.write('throw LuaError() << "Trying to remove element beyond end (dest " << dest << ", length " << {}.size() << ").";'.format(prop.name))

                    # notify
                    body.write(build_notify(mclass, remove_method, dest_index))

                    # save undo
                    body.write('auto element = std::move({}[dest]);'.format(prop.name))
                    body.write('level.add(std::make_shared<function_reaction_t>(')
                    with body.indent():
                        body.write('[this, dest_index, element](std::shared_ptr<undo_level_t> level)')
                    body.write('{')
                    with body.indent():
                        body.write('{}(level, dest, element);'.format(add_method.name))
                    body.write('}));')
                    
                    # modify
                    body.write('{p}.erase({p}.begin() + dest);'.format(p=prop.name))
                    handle_discard_add(body, 'element')

                    return body.f
                remove_method.body = remove_body()
                def order_body():
                    body = Context()
                    body.write('auto element = {}[source];'.format(prop.name))
                    body.write('{}(level, source);'.format(remove_method.name))
                    body.write('if (dest > source)')
                    with body.indent():
                        body.write('{}(level, dest - 1, std::move(element));')
                    body.write('else')
                    with body.indent():
                        body.write('{}(level, dest, std::move(element));')
                    return body.f
                order_method.body = order_body()
                
                mclass.add_method(add_method)
                mclass.add_method(remove_method)
                mclass.add_method(order_method)
            elif isinstance(prop.type, (TInt32, TInt64, TUInt64, TFloat, TBool, TString, MClass)):
                element = MVar(name='element', type=prop.type)
                set_method = MFunction(
                    name='{}_set'.format(prop.name),
                    ret=void,
                    args=MArgs(
                        args=[
                            level,
                            element,
                        ],
                    ),
                    writelua=True,
                )
                def set_body():
                    body = Context()

                    # save undo
                    body.write('level.add(std::make_shared<function_reaction_t>(')
                    with body.indent():
                        body.write('[this, {}](std::shared_ptr<undo_level_t> level)'.format(prop.name))
                    with body.block():
                        body.write('set(level, std::move({}));'.format(prop.name))

                    # modify
                    handle_discard_add(body, prop.name)
                    handle_discard_remove(body, 'element')
                    body.write('{} = std::move(element);'.format(prop.name))

                    # notify
                    body.write(build_notify(mclass, set_method))
                    return body.f
                set_method.body = set_body()
                
                mclass.add_method(set_method)
            else:
                raise AssertionError('Unhandled property type {}'.format(prop.type))
