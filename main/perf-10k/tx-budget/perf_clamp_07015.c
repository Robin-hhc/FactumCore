/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_07015(unsigned int count)
{
    const unsigned int limit = 241u;
    return count > limit ? limit : count;
}
