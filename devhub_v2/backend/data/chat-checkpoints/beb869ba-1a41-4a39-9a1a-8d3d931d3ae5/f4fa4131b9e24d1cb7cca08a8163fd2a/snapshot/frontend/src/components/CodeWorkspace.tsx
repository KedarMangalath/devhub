export default function CodeWorkspace({ treeNodes, selectedFile, expandedDirs, toggleDirectory, loadFile }: any) {
  const renderTreeNode = (node: any, depth = 0) => (
    <div key={node.path}>
      <button
        type="button"
        onClick={() => (node.type === 'directory' ? toggleDirectory(node.path) : loadFile(node.path))}
        className={`flex w-full items-center gap-1 rounded-md py-1 pr-3 text-left text-[11px] ${selectedFile === node.path ? 'bg-[#37373d] text-white' : 'text-[#cccccc] hover:bg-[#2a2d2e] hover:text-white'}`}
      >
        <span>{node.name}</span>
      </button>
    </div>
  );
  return <div>{treeNodes.map((node: any) => renderTreeNode(node))}</div>;
}