#!/usr/bin/env python3
"""
Add --id option to co run command to run specific tasks
"""

def add_id_option():
    """Add --id option to the run command"""
    
    file_path = "claude_orchestrator/main.py"
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # 1. Add --id argument to parser
    parser_args = '''    parser.add_argument('--working-dir', '-d',
                       help='Set working directory for task execution')
    
    # Add command specific arguments (using arg2 as a generic second argument)
    parser.add_argument('arg2', nargs='?','''
    
    parser_args_new = '''    parser.add_argument('--working-dir', '-d',
                       help='Set working directory for task execution')
    
    parser.add_argument('--id', type=str,
                       help='Run only a specific task by ID (e.g., --id 123)')
    
    # Add command specific arguments (using arg2 as a generic second argument)
    parser.add_argument('arg2', nargs='?','''
    
    content = content.replace(parser_args, parser_args_new)
    print("✅ Added --id argument to parser")
    
    # 2. Update run command handler to filter tasks by ID
    run_handler = '''    elif args.command == 'run' or args.command is None:
        # Default behavior - run orchestrator
        # Override config with command line args if provided
        if hasattr(args, 'workers') and args.workers:
            if hasattr(config, 'config_manager'):
                # Enhanced config system
                config.config_manager.config["execution"]["max_workers"] = args.workers
            else:
                # Legacy config system
                config.config["execution"]["max_workers"] = args.workers
        
        # Get working directory from args or config
        working_dir = getattr(args, 'working_dir', None)'''
    
    run_handler_new = '''    elif args.command == 'run' or args.command is None:
        # Default behavior - run orchestrator
        # Override config with command line args if provided
        if hasattr(args, 'workers') and args.workers:
            if hasattr(config, 'config_manager'):
                # Enhanced config system
                config.config_manager.config["execution"]["max_workers"] = args.workers
            else:
                # Legacy config system
                config.config["execution"]["max_workers"] = args.workers
        
        # Check if specific task ID is requested
        specific_task_id = getattr(args, 'id', None)
        if specific_task_id:
            logger.info(f"Running only task with ID: {specific_task_id}")
        
        # Get working directory from args or config
        working_dir = getattr(args, 'working_dir', None)'''
    
    content = content.replace(run_handler, run_handler_new)
    print("✅ Added task ID handling in run command")
    
    # 3. Pass task ID to orchestrator
    orchestrator_init = '''        # Create and run orchestrator
        orchestrator = ClaudeOrchestrator(working_dir=working_dir, config=config)
        orchestrator.run()'''
    
    orchestrator_init_new = '''        # Create and run orchestrator
        orchestrator = ClaudeOrchestrator(working_dir=working_dir, config=config)
        
        # Pass specific task ID if provided
        if specific_task_id:
            orchestrator.run_specific_task(specific_task_id)
        else:
            orchestrator.run()'''
    
    content = content.replace(orchestrator_init, orchestrator_init_new)
    print("✅ Updated orchestrator initialization")
    
    # 4. Add run_specific_task method to ClaudeOrchestrator
    run_method = '''    def run(self):
        """Run the orchestrator"""
        self.start_time = time.time()
        logger.info("\\n" + "="*50)
        logger.info("Starting Claude Orchestrator")
        logger.info("="*50)'''
    
    run_method_new = '''    def run_specific_task(self, task_id: str):
        """Run only a specific task by ID"""
        self.start_time = time.time()
        logger.info("\\n" + "="*50)
        logger.info(f"Starting Claude Orchestrator - Single Task Mode (ID: {task_id})")
        logger.info("="*50)
        
        # Get all tasks and filter by ID
        tasks = self.manager.analyze_and_plan()
        
        # Find the specific task
        target_task = None
        for task in tasks:
            # Handle both string and int IDs
            if str(task.task_id) == str(task_id):
                target_task = task
                break
        
        if not target_task:
            logger.error(f"Task with ID '{task_id}' not found!")
            logger.info("Available task IDs:")
            for task in tasks[:10]:  # Show first 10
                logger.info(f"  - {task.task_id}: {task.title}")
            if len(tasks) > 10:
                logger.info(f"  ... and {len(tasks) - 10} more")
            return
        
        # Check if task is already completed
        task_master = TaskManager()
        tm_task = task_master.get_task(str(task_id))
        if tm_task and tm_task.status == "done":
            logger.warning(f"Task {task_id} is already marked as completed.")
            response = input("Do you want to run it again? (y/n): ")
            if response.lower() != 'y':
                logger.info("Skipping completed task.")
                return
        
        logger.info(f"\\nRunning task: {target_task.title}")
        logger.info(f"Description: {target_task.description}")
        
        # Run with just this one task
        self._run_with_tasks([target_task])
    
    def run(self):
        """Run the orchestrator"""
        self.start_time = time.time()
        logger.info("\\n" + "="*50)
        logger.info("Starting Claude Orchestrator")
        logger.info("="*50)'''
    
    content = content.replace(run_method, run_method_new)
    print("✅ Added run_specific_task method")
    
    # 5. Refactor run method to use _run_with_tasks
    refactor_run = '''        # Get tasks from Task Master
        tasks = self.manager.analyze_and_plan()
        
        if not tasks:
            logger.info("No tasks to process!")
            return
        
        # Initialize components
        self._initialize_workers(len(tasks))'''
    
    refactor_run_new = '''        # Get tasks from Task Master
        tasks = self.manager.analyze_and_plan()
        
        if not tasks:
            logger.info("No tasks to process!")
            return
        
        self._run_with_tasks(tasks)
    
    def _run_with_tasks(self, tasks: List[WorkerTask]):
        """Run orchestrator with specific tasks"""
        # Initialize components
        self._initialize_workers(len(tasks))'''
    
    content = content.replace(refactor_run, refactor_run_new)
    print("✅ Refactored run method to support task filtering")
    
    # 6. Update help text
    help_text = '''  co run                               # Run the orchestrator
  co run --workers 5                   # Run with 5 parallel workers'''
    
    help_text_new = '''  co run                               # Run the orchestrator
  co run --workers 5                   # Run with 5 parallel workers
  co run --id 123                      # Run only task with ID 123'''
    
    content = content.replace(help_text, help_text_new)
    print("✅ Updated help text")
    
    # Save the updated file
    with open(file_path, 'w') as f:
        f.write(content)
    
    print("\n✅ Successfully added --id option to co run command!")
    

def main():
    print("🔧 Adding --id option to co run command...")
    print("-" * 60)
    
    add_id_option()
    
    print("-" * 60)
    print("\n📝 Usage examples:")
    print("  co run --id 123        # Run task 123")
    print("  co run --id task-abc   # Run task with string ID")
    print("  co run --id 42 --workers 1  # Run task 42 with 1 worker")
    print("\nThe command will:")
    print("  - Find the specific task by ID")
    print("  - Check if it's already completed")
    print("  - Run only that task (skipping others)")


if __name__ == "__main__":
    main()