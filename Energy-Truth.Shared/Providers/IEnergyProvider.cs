using System;
using System.Collections.Generic;
using System.Text;
using CsvHelper;

namespace Energy_Truth.Shared.Providers
{
    public interface IEnergyProvider
    {
        string Name { get; }        
        bool IsCumulative { get; }
        CsvMode CsvMode { get; }
        string Delimiter { get; }
        bool StripRowQuotes { get; }
        string DateFormat { get; }

        Dictionary<string, string> CsvMapping { get; }
        Dictionary<string, string> DisplayNames { get; }
    }
}
