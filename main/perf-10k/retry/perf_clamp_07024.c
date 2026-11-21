/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_07024(unsigned int count)
{
    const unsigned int limit = 145u;
    return count > limit ? limit : count;
}
