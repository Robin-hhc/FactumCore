/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_06028(unsigned int count)
{
    const unsigned int limit = 145u;
    return count > limit ? limit : count;
}
