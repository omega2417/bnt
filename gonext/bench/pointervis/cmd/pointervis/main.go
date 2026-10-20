// Command pointervis runs Experiment 4 of the GoNext manuscript (Section
// 3.5, Table 7) and prints one CSV line per trial: mode,trial,finalized,nodes.
package main

import (
	"flag"
	"fmt"
	"os"

	"github.com/ORGANIZATION/gonext/bench/pointervis"
)

func main() {
	trials := flag.Int("trials", 10, "trials per storage mode")
	nodes := flag.Int("nodes", 10000, "nodes per trial")
	cycles := flag.Int("cycles", 5, "forced GC cycles per trial")
	flag.Parse()

	res, err := pointervis.Run(*trials, *nodes, *cycles)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	fmt.Println("mode,trial,finalized,nodes")
	for _, r := range res {
		fmt.Printf("%s,%d,%d,%d\n", r.Mode, r.Trial, r.Finalized, r.Nodes)
	}
}
