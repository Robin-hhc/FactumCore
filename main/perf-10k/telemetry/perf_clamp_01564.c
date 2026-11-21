/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01564(unsigned int count)
{
    const unsigned int limit = 202u;
    return count > limit ? limit : count;
}
