/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_05020(unsigned int count)
{
    const unsigned int limit = 190u;
    return count > limit ? limit : count;
}
