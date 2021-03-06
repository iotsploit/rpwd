#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author: 'arvin'
from prettytable import PrettyTable

import utils
import threads
from template.interpreter import BaseInterpreter, scan_result_queue
from template.scanner import ScanTask
from exceptions import BadHostInfoException, ModuleImportException


class Interpreter(BaseInterpreter):
    def __init__(self):
        super(Interpreter, self).__init__()
        self.last_result = []
        self.prompt_module = 'Scanner'
        self.module = None
        self.modules = utils.index_modules(modules_directory='/'.join((utils.MODULES_DIR, 'scanner/')))
        self.files = utils.list_files('./')
        self.sub_opt = {'task': ['add', 'timeout', 'threads', 'file', 'output', 'emptyhosts'],
                        # 'show': ['host', 'port', 'output', 'all'],
                        }
        self.task = ScanTask()
        self.cmdloop()

    def change_prompt(self, scanner):
        self.prompt_module = scanner.prompt
        self.generate_prompt()

    def do_load(self, scanner_name):
        module_path = utils.pythonize_path(scanner_name)
        module_path = '.'.join(('modules.scanner', module_path))
        try:
            self.module = utils.import_module(module_path, 'Scanner')
        except ModuleImportException as err:
            utils.print_failed(err)
        else:
            self.change_prompt(self.module)

    # def do_unload(self, args):
    #     self.module = None
    #     self.prompt_module = 'Scanner'
    #     self.generate_prompt()

    def complete_load(self, text, line, *args, **kwargs):
        available_modules = [s for s in self.modules if s.startswith(text)]

        def split_modules(available_module):
            head, _, tail = available_module[len(text):].partition('.')
            if head:
                return text + head
            if not head and not tail:
                # indicates available_module[len(text)] is empty ''
                return
            else:
                # indicates available_module[len(text)] begins with '.'
                next_head, _, _ = tail.partition('.')
                return text + '.' + next_head

        return list(map(split_modules, available_modules))

    def do_task(self, args):
        try:
            sub_opt, arg = args.split(' ')[0], args.split(' ')[1:]
            if sub_opt not in self.sub_opt['task']:
                raise BadHostInfoException()
        except IndexError:
            utils.print_failed("Error during setting '{}'\n"
                               "Not enough arguments\n"
                               "Use <tab> key multiple times for completion.".format(args))
            return
        except BadHostInfoException as err:
            utils.print_failed("Error during setting '{}'\n"
                               "Use <tab> key multiple times for completion.".format(args))
            return
        try:
            self.task.__getattribute__(sub_opt)(arg)
        except (BadHostInfoException, TypeError) as err:
            utils.print_failed("Error during setting '{}'\n"
                               "{}.\n"
                               "Please check the arguments input.".format(sub_opt, err))

    def complete_task(self, text, line, *args):
        if len(line.split(' ')) > 2:
            return [' '.join((attr, '')) for attr in self.files if attr.startswith(text)]
        else:
            return self.auto_complete(text, 'task')

    def do_show(self, arg):
        self.task.show()

    def do_check(self, arg):
        pass

    def do_run(self, arg):
        scan_result_queue.empty()
        self.last_result = []
        utils.print_info('checking if module loaded')
        if not self.check_module_loaded():
            utils.print_failed('checking module failed\n'
                               'Please make sure you have already choose one module')
            return

        utils.print_info('checking targets info')
        if not self.check_task_arg():
            utils.print_failed('checking targets info failed\n'
                               'Please make sure you input info target info')
            return
        else:
            utils.print_success('passing checking...')

        with threads.ThreadPoolExecutor(self.task.get_threads()) as executor:
            for target in self.task.get_targets():
                executor.submit(self.target_func, target)

        utils.print_success('all tasks finished...')

        while True:
            try:
                result = scan_result_queue.get(block=False)
                self.last_result.append(result)
            except Exception as e:
                print(e)
                break

        if self.task.get_output() != '':
            fd = open(self.task.get_output(), 'w')
            for result in self.last_result:
                utils.print_info(
                    "{}:{},{},{},{},{}".format(result.host, result.port, result.brand, result.module, result.extra,
                                               result.exploit), file=fd)
            fd.close()

    def do_back(self, *arg):
        return True

    def do_result(self, *args):
        x = PrettyTable()
        x.field_names = ['host', 'port', 'brand', 'module', 'extra', 'exploit']
        for result in self.last_result:
            x.add_row(result)

        utils.print_info(x)

    def do_emptyresult(self, *args):
        utils.print_warning('are you sure to clear all result? ')
        user_input = input('Y/N:')
        if user_input.lower() == 'y' or user_input.lower() == 'yes':
            self.last_result = []
            utils.print_info('clear all last results')

    def do_writeresult(self, *args):
        if self.task.get_output():
            fd = open(self.task.get_output(), 'w')
            for result in self.last_result:
                utils.print_info(
                    "{}:{},{},{},{},{}".format(result.host, result.port, result.brand, result.module, result.extra,
                                               result.exploit), file=fd)

            fd.close()
        else:
            utils.print_failed('no output file given')

    def complete_show(self, text, *args):
        return self.auto_complete(text, 'show')

    def auto_complete(self, text, opt):
        if text:
            return [' '.join((attr, '')) for attr in self.sub_opt[opt] if attr.startswith(text)]
        else:
            return self.sub_opt[opt]

    def check_task_arg(self):
        if len(self.task.get_targets()) > 0:
            return True
        else:
            return False

    def check_module_loaded(self):
        if self.module:
            return True
        else:
            return False

    def target_func(self, target):
        self.module().scan(target.host, target.port, self.task.get_timeout())
