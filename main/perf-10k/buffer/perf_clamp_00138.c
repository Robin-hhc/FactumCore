/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_00138(unsigned int count)
{
    const unsigned int limit = 113u;
    return count > limit ? limit : count;
}
