/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_00388(unsigned int count)
{
    const unsigned int limit = 130u;
    return count > limit ? limit : count;
}
