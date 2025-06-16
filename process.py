import pdb

def main():

    infilename = "pt_br_50k.txt"
    outfilename = "portuguese.txt"
    
    # read
    lines = None
    with open(infilename, 'r') as infile:
        lines = [line.split()[0] for line in infile.readlines()]

    # write
    with open(outfilename, 'w') as outfile:
            outfile.writelines([f"{line}\n" for line in lines])
            





if __name__ == "__main__":
    main()

